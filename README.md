# Daily Financial News Scanner

Scrapes free financial news RSS feeds every day, figures out which forex
pairs and stocks a headline is likely to move, scores the sentiment, pulls
price data, and generates a systematic entry / stop-loss / take-profit
level for anything with a clear directional signal.

**No API keys required.** Runs entirely on free data sources.

## ⚠️ Read this first

The "entry/SL/TP" levels are produced by a rules-based system:
- Direction comes from aggregated news sentiment (VADER + a finance
  phrase lexicon).
- Stop-loss = recent swing high/low, padded by ATR.
- Take-profit = a fixed risk:reward multiple (default 1:2) of the stop
  distance, capped/flagged if it runs past recent structure.

This is a **consistent methodology**, not a guarantee. No headline
scanner can produce a "perfect" trade — treat every output as a
starting point for your own confirmation, not a signal to execute
blindly. Position-size accordingly.

## How the pipeline works

```
scraper.py            → pulls headlines from free RSS feeds
entity_matcher.py      → links headlines to forex pairs / S&P 500 stocks
sentiment_engine.py     → scores each headline (local, no API)
technical_analysis.py   → pulls OHLC (yfinance) → ATR, trend, swing levels → entry/SL/TP
report_generator.py     → compiles the daily markdown report
main.py                 → orchestrates all of the above
```

Sentiment is **aggregated per instrument across the day's headlines**
before any trade level is generated — a single headline won't trigger a
setup; the system waits for a clear (non-neutral) average across
everything published that day. This avoids overreacting to one noisy
story.

## Running it once, locally

```bash
pip install -r requirements.txt
python main.py
```

This writes `reports/YYYY-MM-DD.md` and prints it to the console.

## Running it automatically, forever, with zero manual work

This is the setup that matches "runs on its own, no daily input from me."

1. **Create a GitHub repo** (private is fine) and push this folder to it:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```

2. **That's it for setup.** The included workflow at
   `.github/workflows/daily_scan.yml` is already configured to:
   - Run every weekday at 07:00 UTC (edit the `cron:` line to change the time)
   - Install dependencies fresh each run
   - Execute `main.py`
   - Commit the day's report into `reports/`
   - **Open a GitHub Issue containing the full report**

3. **Get notified automatically:** click **Watch → All Activity** on your
   repo (top-right of the GitHub repo page). GitHub will email you every
   time the daily workflow opens a new Issue — that's your daily digest,
   with no bot, no email server, and no API key of your own required.

4. Optional — trigger it on demand any time: go to the **Actions** tab →
   *Daily Financial News Scan* → **Run workflow**.

### Why GitHub Actions and not "Claude runs it for you"

Claude doesn't have a persistent server it can leave running in the
background on your behalf — each conversation's environment is
temporary. GitHub Actions' free tier is the closest equivalent: a
scheduler that isn't your machine, doesn't need to stay powered on, and
doesn't require you to do anything once the cron job is committed.

## Track record (does it actually work?)

Every setup the scanner generates gets logged to `reports/tracked_setups.json`.
On each subsequent run, the scanner checks every still-open logged setup
against real daily price action:

- If a day's Low (for a bullish setup) or High (for a bearish setup)
  touches the stop-loss, it's logged as a loss.
- If price reaches the take-profit first, it's logged as a win.
- If neither happens within 14 days, it's marked expired/unresolved
  (and noted whether price at least moved the right direction).

**One real limitation, stated plainly:** this uses daily bars, not
intraday data. If a single day's range touches both the stop and the
target, there's no way to tell which happened first from daily data
alone — the checker resolves that conservatively as a loss, so the
tracked win rate is never flattered by an unresolvable tie.

The dashboard's **Track Record** panel shows win rate by confidence
tier (HIGH / MEDIUM / LOW), so you can see directly whether the
confidence scoring actually means anything, or whether e.g. LOW
setups perform the same as HIGH ones (in which case the confidence
heuristic needs rethinking).

## Viewing results locally (dashboard)

Every run now also writes structured JSON (`reports/YYYY-MM-DD.json` and
`reports/index.json`) alongside the markdown report, and there's a small
static dashboard at `dashboard/index.html` that reads them.

```bash
# from the repo root
python -m http.server 8000
```

Then open **http://localhost:8000/dashboard/index.html** in your browser.
Use the date dropdown (top right) to switch days, click a row to expand
its ATR/swing/trend detail, and click a column header to sort.

You have to use a local server (not just double-clicking the HTML file) —
browsers block a plain `file://` page from fetching the JSON files next to
it. `python -m http.server` is the simplest way around that; it's already
installed if you have Python.

The dashboard is entirely static (no build step, no dependencies) — it
just reads whatever's in `reports/`, so it always reflects your latest
GitHub Actions run once you `git pull` the updated `reports/` folder
locally, or if you run `main.py` locally yourself.

## Customizing

- **Watchlist**: edit `FOREX_PAIRS` and `EXTRA_INSTRUMENTS` in `config.py`.
  Stocks are loaded from the full S&P 500 (`data/sp500_raw.csv`) — trim
  that file if you only care about specific names.
- **News sources**: add/remove feeds in `RSS_FEEDS` in `config.py`. Any
  RSS/Atom feed URL works.
- **Risk parameters**: `ATR_PERIOD`, `SWING_LOOKBACK`, `RISK_REWARD_RATIO`,
  `MIN_SENTIMENT_ABS` in `config.py`.
- **Schedule**: the `cron:` line in `.github/workflows/daily_scan.yml`
  (cron times are UTC).

## Known limitations

- RSS feeds occasionally change structure or go down — the scraper skips
  a dead feed rather than failing the whole run, but check the Action
  logs periodically.
- Company-name matching is keyword-based, not NLP entity recognition —
  it will occasionally miss indirect references or catch a false
  positive on an ambiguous name. Treat matches as a starting filter, not
  ground truth.
- Free RSS feeds are a much thinner news set than a paid terminal
  (Bloomberg, Reuters Eikon) — this is a "good coverage for zero cost"
  tool, not an institutional-grade feed.
