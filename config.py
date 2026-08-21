"""
Central configuration for the Financial News Scanner.
Edit the lists below to change what the scanner tracks.
"""

# ── FOREX WATCHLIST ──────────────────────────────────────────────
# yfinance ticker format for FX pairs is "EURUSD=X"
FOREX_PAIRS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X",
    "AUDUSD=X", "USDCAD=X", "NZDUSD=X", "EURGBP=X",
    "EURJPY=X", "GBPJPY=X",
]

# Extra instruments some traders lump in with "forex" scans
EXTRA_INSTRUMENTS = {
    "GC=F": "Gold",
    "SI=F": "Silver",
    "BTC-USD": "Bitcoin",
    "NQ=F": "Nasdaq Futures",
}

# ── CURRENCY → KEYWORD MAP ───────────────────────────────────────
# Used to link a news headline/summary to a currency by matching
# country names, central banks, and officials' institutional titles.
CURRENCY_KEYWORDS = {
    "USD": ["federal reserve", "fed ", "fomc", "jerome powell", "u.s. economy",
            "united states economy", "us inflation", "us cpi", "us jobs",
            "nonfarm payroll", "treasury yields", "dollar index", "dxy"],
    "EUR": ["european central bank", "ecb", "eurozone", "euro area",
            "christine lagarde", "germany economy", "france economy",
            "eu inflation"],
    "GBP": ["bank of england", "boe ", "uk economy", "britain economy",
            "andrew bailey", "uk inflation", "uk cpi", "sterling"],
    "JPY": ["bank of japan", "boj", "kazuo ueda", "japan economy",
            "yen ", "japan inflation"],
    "CHF": ["swiss national bank", "snb", "switzerland economy", "franc"],
    "AUD": ["reserve bank of australia", "rba", "australia economy",
            "aussie dollar"],
    "CAD": ["bank of canada", "boc ", "canada economy", "loonie"],
    "NZD": ["reserve bank of new zealand", "rbnz", "new zealand economy",
            "kiwi dollar"],
}

# Macro terms that raise the "market-moving" score of a headline
# regardless of which currency/stock it's tied to.
HIGH_IMPACT_TERMS = [
    "interest rate", "rate hike", "rate cut", "rate decision",
    "inflation", "cpi", "gdp", "unemployment", "nonfarm payroll",
    "jobs report", "recession", "quantitative easing", "tapering",
    "earnings", "guidance", "downgrade", "upgrade", "bankruptcy",
    "merger", "acquisition", "lawsuit", "sec investigation",
    "stock split", "dividend", "buyback", "ceo", "resigns", "layoffs",
    "tariff", "sanctions", "war", "conflict", "election",
]

# ── STOCK WATCHLIST ──────────────────────────────────────────────
# Loaded at runtime from data/sp500_raw.csv (full S&P 500).
# You can shrink this if you only care about specific names —
# just replace load_stock_watchlist() usage with a fixed list.
SP500_CSV_PATH = "data/sp500_raw.csv"

# ── NEWS SOURCES (free RSS, no API key required) ────────────────
RSS_FEEDS = {
    "Investing.com - Forex":      "https://www.investing.com/rss/news_1.rss",
    "Investing.com - Economy":    "https://www.investing.com/rss/news_95.rss",
    "Investing.com - Stock Mkt":  "https://www.investing.com/rss/news_25.rss",
    "Yahoo Finance":              "https://finance.yahoo.com/news/rssindex",
    "MarketWatch - Top Stories":  "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "MarketWatch - Markets":      "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
    "FXStreet - News":            "https://www.fxstreet.com/rss/news",
    "CNBC - Markets":             "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
}

# ── ANALYSIS PARAMETERS ──────────────────────────────────────────
LOOKBACK_DAYS = 90          # how much OHLC history to pull per instrument
ATR_PERIOD = 14
SWING_LOOKBACK = 20         # bars used to find recent swing high/low
RISK_REWARD_RATIO = 2.0     # TP distance = RR * SL distance
MIN_SENTIMENT_ABS = 0.25    # |compound sentiment| below this = "no clear bias", skipped
MAX_HEADLINES_PER_RUN = 300 # safety cap across all feeds

# ── TRACK RECORD ──────────────────────────────────────────────
TRACKED_SETUPS_PATH = "reports/tracked_setups.json"
EXPIRY_CALENDAR_DAYS = 14   # a setup neither hitting SL nor TP within this
                            # many days is marked EXPIRED (unresolved)
