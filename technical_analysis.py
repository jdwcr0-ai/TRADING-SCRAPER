"""
technical_analysis.py — pulls price history (free, via yfinance) and
turns it + a news-sentiment bias into a systematic entry/SL/TP
suggestion.

IMPORTANT: this is a rules-based systematic framework, not a
guarantee. ATR-based stops and R:R-based targets are a common,
defensible methodology — they are not "perfect" trades. That
caveat is baked into the output on purpose.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from config import LOOKBACK_DAYS, ATR_PERIOD, SWING_LOOKBACK, RISK_REWARD_RATIO


@dataclass
class TradeSetup:
    ticker: str
    bias: str              # BULLISH / BEARISH / NEUTRAL
    last_close: float
    atr: float
    swing_high: float
    swing_low: float
    trend_aligned: bool
    entry: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    risk_reward: float
    confidence: str        # LOW / MEDIUM / HIGH
    notes: list[str]


def fetch_price_history(ticker: str, days: int = LOOKBACK_DAYS) -> Optional[pd.DataFrame]:
    try:
        df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < ATR_PERIOD + 2:
            return None
        # yfinance sometimes returns MultiIndex columns for a single ticker
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return None


def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return float(atr)


def compute_trend(df: pd.DataFrame) -> str:
    """Simple EMA20 vs EMA50 trend read."""
    close = df["Close"]
    ema_fast = close.ewm(span=20, adjust=False).mean().iloc[-1]
    ema_slow = close.ewm(span=50, adjust=False).mean().iloc[-1] if len(close) >= 50 else close.mean()
    if ema_fast > ema_slow:
        return "BULLISH"
    if ema_fast < ema_slow:
        return "BEARISH"
    return "NEUTRAL"


def build_trade_setup(ticker: str, news_bias: str, sentiment_strength: float) -> Optional[TradeSetup]:
    df = fetch_price_history(ticker)
    if df is None:
        return None

    notes = []
    last_close = float(df["Close"].iloc[-1])
    atr = compute_atr(df)
    swing_high = float(df["High"].iloc[-SWING_LOOKBACK:].max())
    swing_low = float(df["Low"].iloc[-SWING_LOOKBACK:].min())
    price_trend = compute_trend(df)

    trend_aligned = (price_trend == news_bias)
    if not trend_aligned:
        notes.append(
            f"News sentiment ({news_bias}) conflicts with the price trend "
            f"({price_trend}) — treat this setup with extra caution."
        )

    entry = stop_loss = take_profit = None
    if news_bias == "BULLISH":
        entry = last_close
        stop_loss = min(swing_low, entry - 0.5 * atr)
        risk = entry - stop_loss
        take_profit = entry + RISK_REWARD_RATIO * risk
        if take_profit > swing_high and (swing_high - entry) > 0:
            notes.append(
                f"Calculated target ({take_profit:.5f}) is beyond recent swing "
                f"resistance ({swing_high:.5f}) — consider scaling out there first."
            )
    elif news_bias == "BEARISH":
        entry = last_close
        stop_loss = max(swing_high, entry + 0.5 * atr)
        risk = stop_loss - entry
        take_profit = entry - RISK_REWARD_RATIO * risk
        if take_profit < swing_low and (entry - swing_low) > 0:
            notes.append(
                f"Calculated target ({take_profit:.5f}) is beyond recent swing "
                f"support ({swing_low:.5f}) — consider scaling out there first."
            )
    else:
        notes.append("Sentiment is neutral/mixed — no directional bias, no trade levels generated.")

    # crude confidence score: trend alignment + sentiment strength + ATR sanity
    score = 0
    if trend_aligned:
        score += 1
    if abs(sentiment_strength) >= 0.5:
        score += 1
    if atr > 0 and last_close > 0 and (atr / last_close) < 0.05:
        score += 1  # not in an abnormally volatile regime
    confidence = {0: "LOW", 1: "LOW", 2: "MEDIUM", 3: "HIGH"}[score]

    rr = RISK_REWARD_RATIO if entry is not None else 0.0

    return TradeSetup(
        ticker=ticker, bias=news_bias, last_close=last_close, atr=atr,
        swing_high=swing_high, swing_low=swing_low, trend_aligned=trend_aligned,
        entry=entry, stop_loss=stop_loss, take_profit=take_profit,
        risk_reward=rr, confidence=confidence, notes=notes,
    )


if __name__ == "__main__":
    setup = build_trade_setup("EURUSD=X", "BULLISH", 0.6)
    if setup:
        print(setup)
    else:
        print("No data returned (expected in a network-restricted sandbox).")
