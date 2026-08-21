"""
entity_matcher.py — links a NewsItem to the forex pairs / stocks it
plausibly affects, using keyword and company-name matching. This is
deliberately simple (no ML/API dependency) so it runs anywhere for free.
"""
from __future__ import annotations
import csv
import re
from dataclasses import dataclass, field
from typing import List, Dict

from config import (
    CURRENCY_KEYWORDS, HIGH_IMPACT_TERMS, FOREX_PAIRS,
    EXTRA_INSTRUMENTS, SP500_CSV_PATH,
)
from scraper import NewsItem


@dataclass
class StockRef:
    symbol: str
    name: str
    sector: str


def load_stock_watchlist(path: str = SP500_CSV_PATH) -> List[StockRef]:
    stocks = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stocks.append(StockRef(
                symbol=row["Symbol"].strip(),
                name=row["Security"].strip(),
                sector=row.get("GICS Sector", "").strip(),
            ))
    return stocks


# Pairs of currencies that make up each FX ticker, e.g. EURUSD=X -> (EUR, USD)
def _currency_pair(ticker: str) -> tuple[str, str]:
    base = ticker.replace("=X", "")
    return base[:3], base[3:]


# Words too generic to safely identify a single company on their own —
# multiple S&P 500 names start with these (e.g. "Bank of America" vs
# "Bank of England" in ordinary financial news), or they double as
# everyday macro vocabulary. Skip them as shorthand match keys.
_GENERIC_STOPWORDS = {
    "bank", "national", "united", "american", "general", "international",
    "global", "group", "home", "real", "public", "first", "west", "north",
    "south", "east", "central", "trust", "financial", "corp", "inc", "the",
    "new", "old", "capital", "united", "world", "state", "states", "one",
    "prudential", "regions",  # ambiguous with everyday words in headlines
}


def _build_stock_lookup(stocks: List[StockRef]) -> Dict[str, StockRef]:
    """Map lowercase company-name tokens/full names to StockRef for fast matching."""
    lookup = {}
    seen_first_words: dict[str, int] = {}
    for s in stocks:
        lookup[s.name.lower()] = s
        first_word = re.split(r"[ ,.]", s.name)[0].lower()
        seen_first_words[first_word] = seen_first_words.get(first_word, 0) + 1

    for s in stocks:
        first_word = re.split(r"[ ,.]", s.name)[0].lower()
        # Only use the first word as shorthand if: it's long enough to be
        # distinctive, isn't a generic/macro word, and isn't shared by
        # more than one company in the watchlist (ambiguous otherwise).
        if (len(first_word) > 3
                and first_word not in _GENERIC_STOPWORDS
                and seen_first_words[first_word] == 1):
            lookup.setdefault(first_word, s)
    return lookup


@dataclass
class MatchResult:
    news: NewsItem
    currencies: List[str] = field(default_factory=list)
    stocks: List[StockRef] = field(default_factory=list)
    impact_terms: List[str] = field(default_factory=list)

    @property
    def is_relevant(self) -> bool:
        return bool(self.currencies or self.stocks)


def match_news(news_items: List[NewsItem], stocks: List[StockRef]) -> List[MatchResult]:
    stock_lookup = _build_stock_lookup(stocks)
    results = []

    for item in news_items:
        text_lower = item.text.lower()
        matched_currencies = []
        matched_stocks = []
        matched_terms = []

        # currency keyword matching
        for ccy, keywords in CURRENCY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                matched_currencies.append(ccy)

        # ticker symbol matching (e.g. "$AAPL" or standalone "AAPL")
        for sym_match in re.findall(r"\$([A-Z]{1,5})\b", item.text):
            hit = next((s for s in stocks if s.symbol == sym_match), None)
            if hit and hit not in matched_stocks:
                matched_stocks.append(hit)

        # company name matching
        for key, stock in stock_lookup.items():
            if key in text_lower and stock not in matched_stocks:
                matched_stocks.append(stock)

        # high-impact macro terms (for scoring / prioritization)
        for term in HIGH_IMPACT_TERMS:
            if term in text_lower:
                matched_terms.append(term)

        results.append(MatchResult(
            news=item,
            currencies=matched_currencies,
            stocks=matched_stocks[:5],  # cap noise from generic word collisions
            impact_terms=matched_terms,
        ))

    return results


def affected_forex_pairs(matched_currencies: List[str]) -> List[str]:
    """Given currencies mentioned in a story, return which watchlist pairs involve them."""
    hits = []
    for pair in FOREX_PAIRS:
        base, quote = _currency_pair(pair)
        if base in matched_currencies or quote in matched_currencies:
            hits.append(pair)
    return hits


if __name__ == "__main__":
    stocks = load_stock_watchlist()
    print(f"Loaded {len(stocks)} stocks")
    sample = [
        NewsItem("test", "Fed signals rate hike as inflation surges", "", "", ""),
        NewsItem("test", "Apple beats earnings expectations, raises guidance", "", "", ""),
        NewsItem("test", "Bank of England holds rates amid UK inflation concerns", "", "", ""),
    ]
    matches = match_news(sample, stocks)
    for m in matches:
        print(m.news.title)
        print("  currencies:", m.currencies, "-> pairs:", affected_forex_pairs(m.currencies))
        print("  stocks:", [s.symbol for s in m.stocks])
        print("  impact terms:", m.impact_terms)
