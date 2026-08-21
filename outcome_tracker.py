"""
outcome_tracker.py — turns "let's see how it plays out" into an actual
number. Every setup the scanner generates gets logged as OPEN; on each
subsequent run, open setups are checked against real price action to
see whether the stop-loss or take-profit was hit first, or whether
the setup expired unresolved.

Limitation, stated plainly: we only have daily OHLC bars, not
intraday data. If a single day's High touches take-profit AND that
same day's Low touches stop-loss, there's no way to know which
happened first from daily data alone. This checker resolves that
ambiguity conservatively — it assumes the stop was hit first — so
the tracked win rate is never flattered by an unresolvable tie.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, date
from typing import List, Optional

import pandas as pd

from config import TRACKED_SETUPS_PATH, EXPIRY_CALENDAR_DAYS
from technical_analysis import TradeSetup, fetch_price_history


@dataclass
class TrackedSetup:
    ticker: str
    bias: str
    confidence: str
    entry: float
    stop_loss: float
    take_profit: float
    date_opened: str          # ISO date string
    status: str = "OPEN"      # OPEN / HIT_TP / HIT_SL / EXPIRED
    date_resolved: Optional[str] = None
    exit_price: Optional[float] = None
    note: Optional[str] = None


def load_tracked(path: str = TRACKED_SETUPS_PATH) -> List[TrackedSetup]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [TrackedSetup(**r) for r in raw]


def save_tracked(tracked: List[TrackedSetup], path: str = TRACKED_SETUPS_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(t) for t in tracked], f, indent=2)


def _days_between(d1: str, d2: date) -> int:
    return (d2 - datetime.strptime(d1, "%Y-%m-%d").date()).days


def check_open_positions(tracked: List[TrackedSetup]) -> List[TrackedSetup]:
    """Check every OPEN tracked setup against price action since it opened.
    Mutates and returns the same list (resolved items get their status updated)."""
    today = datetime.now(timezone.utc).date()

    # group open setups by ticker so we only pull price history once per ticker
    open_by_ticker: dict[str, List[TrackedSetup]] = {}
    for t in tracked:
        if t.status == "OPEN":
            open_by_ticker.setdefault(t.ticker, []).append(t)

    for ticker, setups in open_by_ticker.items():
        df = fetch_price_history(ticker)
        if df is None:
            continue  # no data this run; leave OPEN, try again next run

        # Defensive: yfinance normally returns a DatetimeIndex, but guard
        # against any caller passing something else (e.g. in tests) rather
        # than crashing the whole daily run over one ticker.
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        for t in setups:
            opened = datetime.strptime(t.date_opened, "%Y-%m-%d").date()
            # only look at bars strictly after the day the setup was opened
            window = df[df.index.date > opened]
            if window.empty:
                continue

            resolved = False
            for idx, row in window.iterrows():
                bar_date = idx.date().isoformat()
                if t.bias == "BULLISH":
                    hit_sl = row["Low"] <= t.stop_loss
                    hit_tp = row["High"] >= t.take_profit
                    if hit_sl:  # conservative: check stop first on an ambiguous day
                        t.status, t.exit_price = "HIT_SL", t.stop_loss
                        t.date_resolved = bar_date
                        if hit_tp:
                            t.note = "Same bar touched both SL and TP; daily data can't tell which came first — scored conservatively as SL hit."
                        resolved = True
                        break
                    if hit_tp:
                        t.status, t.exit_price = "HIT_TP", t.take_profit
                        t.date_resolved = bar_date
                        resolved = True
                        break
                else:  # BEARISH
                    hit_sl = row["High"] >= t.stop_loss
                    hit_tp = row["Low"] <= t.take_profit
                    if hit_sl:
                        t.status, t.exit_price = "HIT_SL", t.stop_loss
                        t.date_resolved = bar_date
                        if hit_tp:
                            t.note = "Same bar touched both SL and TP; daily data can't tell which came first — scored conservatively as SL hit."
                        resolved = True
                        break
                    if hit_tp:
                        t.status, t.exit_price = "HIT_TP", t.take_profit
                        t.date_resolved = bar_date
                        resolved = True
                        break

            if not resolved and _days_between(t.date_opened, today) >= EXPIRY_CALENDAR_DAYS:
                t.status = "EXPIRED"
                t.date_resolved = today.isoformat()
                t.exit_price = float(df["Close"].iloc[-1])
                moved_favorably = (
                    (t.bias == "BULLISH" and t.exit_price > t.entry) or
                    (t.bias == "BEARISH" and t.exit_price < t.entry)
                )
                t.note = (
                    f"Neither level hit within {EXPIRY_CALENDAR_DAYS} days. "
                    f"Price {'moved in the predicted direction but did not reach target' if moved_favorably else 'did not move in the predicted direction'}."
                )

    return tracked


def add_new_setups(tracked: List[TrackedSetup], setups: List[TradeSetup], date_str: str) -> List[TrackedSetup]:
    """Log today's setups as new OPEN entries. Skips anything missing a
    complete entry/SL/TP (e.g. the NaN-guarded cases)."""
    for s in setups:
        if s.entry is None or s.stop_loss is None or s.take_profit is None:
            continue
        tracked.append(TrackedSetup(
            ticker=s.ticker, bias=s.bias, confidence=s.confidence,
            entry=s.entry, stop_loss=s.stop_loss, take_profit=s.take_profit,
            date_opened=date_str,
        ))
    return tracked


def compute_stats(tracked: List[TrackedSetup]) -> dict:
    """Win rate and counts, broken out by confidence tier."""
    tiers = ["HIGH", "MEDIUM", "LOW"]
    stats = {}
    for tier in tiers:
        resolved = [t for t in tracked if t.confidence == tier and t.status in ("HIT_TP", "HIT_SL")]
        wins = [t for t in resolved if t.status == "HIT_TP"]
        open_count = len([t for t in tracked if t.confidence == tier and t.status == "OPEN"])
        expired = [t for t in tracked if t.confidence == tier and t.status == "EXPIRED"]
        stats[tier] = {
            "resolved": len(resolved),
            "wins": len(wins),
            "win_rate": round(len(wins) / len(resolved), 3) if resolved else None,
            "open": open_count,
            "expired": len(expired),
        }
    overall_resolved = [t for t in tracked if t.status in ("HIT_TP", "HIT_SL")]
    overall_wins = [t for t in overall_resolved if t.status == "HIT_TP"]
    stats["OVERALL"] = {
        "resolved": len(overall_resolved),
        "wins": len(overall_wins),
        "win_rate": round(len(overall_wins) / len(overall_resolved), 3) if overall_resolved else None,
        "open": len([t for t in tracked if t.status == "OPEN"]),
        "expired": len([t for t in tracked if t.status == "EXPIRED"]),
    }
    return stats


if __name__ == "__main__":
    # sanity check with synthetic data — no network needed
    import numpy as np

    dates = pd.date_range(end=datetime.now(timezone.utc).date(), periods=10, freq="D")
    df = pd.DataFrame({
        "High":  [101, 102, 103, 104, 105, 106, 108, 110, 111, 112],
        "Low":   [99, 100, 101, 102, 103, 104, 105, 107, 108, 109],
        "Close": [100, 101, 102, 103, 104, 105, 107, 109, 110, 111],
    }, index=dates)

    # NOTE: check_open_positions() looks up fetch_price_history via this
    # module's own globals, so rebind the name directly here (importing a
    # second copy under an alias would patch a different module object).
    global fetch_price_history
    fetch_price_history = lambda ticker, days=90: df

    opened_date = (dates[2]).date().isoformat()
    tracked = [
        TrackedSetup("TEST", "BULLISH", "HIGH", entry=102, stop_loss=99, take_profit=110, date_opened=opened_date),
    ]
    result = check_open_positions(tracked)
    for t in result:
        print(t)
