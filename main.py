"""
main.py — daily orchestrator.

Pipeline:
1. Scrape free RSS feeds for financial news.
2. Match each headline to affected forex pairs / stocks.
3. Aggregate sentiment per instrument (multiple headlines can hit
   the same instrument in one day — combine them rather than
   reacting to a single story).
4. For instruments with a clear (non-neutral) aggregate bias, pull
   price data and generate an entry/SL/TP setup.
5. Render + save a markdown report; print a short summary to stdout
   (this is what shows up in CI logs / a GitHub Issue).
"""
from __future__ import annotations
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone

from config import EXTRA_INSTRUMENTS, MIN_SENTIMENT_ABS
from scraper import fetch_all_news
from entity_matcher import load_stock_watchlist, match_news, affected_forex_pairs
from sentiment_engine import score_text, bias_label
from technical_analysis import build_trade_setup
from report_generator import render_report, save_report, save_json, update_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("main")


def run() -> str:
    log.info("Fetching news...")
    news = fetch_all_news()
    log.info("Fetched %d unique headlines", len(news))

    log.info("Loading stock watchlist...")
    stocks = load_stock_watchlist()

    log.info("Matching news to instruments...")
    matches = match_news(news, stocks)
    relevant = [m for m in matches if m.is_relevant]
    log.info("%d headlines matched an instrument on the watchlist", len(relevant))

    # aggregate sentiment per instrument across all headlines that mention it
    instrument_scores: dict[str, list[float]] = defaultdict(list)

    for m in relevant:
        sc = score_text(m.news.text)
        compound = sc["compound"]

        for pair in affected_forex_pairs(m.currencies):
            instrument_scores[pair].append(compound)
        for stock in m.stocks:
            instrument_scores[stock.symbol].append(compound)

    # build trade setups for instruments with a clear (non-neutral) aggregate bias
    setups = []
    for ticker, scores in instrument_scores.items():
        avg_score = sum(scores) / len(scores)
        if abs(avg_score) < MIN_SENTIMENT_ABS:
            continue  # mixed/neutral news, skip — no false confidence
        bias = bias_label(avg_score, threshold=MIN_SENTIMENT_ABS)
        log.info("Building trade setup for %s (bias=%s, avg_sentiment=%.2f, n_headlines=%d)",
                  ticker, bias, avg_score, len(scores))
        setup = build_trade_setup(ticker, bias, avg_score)
        if setup:
            setups.append(setup)
        else:
            log.warning("No price data available for %s — skipped", ticker)

    report = render_report(setups, headline_count=len(news), matched_count=len(relevant))

    os.makedirs("reports", exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = f"reports/{date_str}.md"
    save_report(report, out_path)
    log.info("Report saved to %s", out_path)

    json_path = f"reports/{date_str}.json"
    save_json(setups, headline_count=len(news), matched_count=len(relevant),
              path=json_path, date_str=date_str)
    update_index("reports")
    log.info("Dashboard data saved to %s (index.json refreshed)", json_path)

    print(report)
    return report


if __name__ == "__main__":
    run()
