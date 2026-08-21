"""
scraper.py — pulls headlines from free RSS feeds.
No API keys required. If a feed is down/blocked it is skipped and
logged, so one dead feed never kills the whole run.
"""
from __future__ import annotations
import time
import logging
from dataclasses import dataclass
from typing import List

import feedparser

from config import RSS_FEEDS, MAX_HEADLINES_PER_RUN

log = logging.getLogger("scraper")


@dataclass
class NewsItem:
    source: str
    title: str
    summary: str
    link: str
    published: str

    @property
    def text(self) -> str:
        """Combined text used for keyword/sentiment matching."""
        return f"{self.title}. {self.summary}"


def fetch_feed(source_name: str, url: str, timeout: int = 15) -> List[NewsItem]:
    items: List[NewsItem] = []
    try:
        parsed = feedparser.parse(url)
        if parsed.bozo and not parsed.entries:
            log.warning("Feed failed to parse cleanly: %s (%s)", source_name, parsed.bozo_exception)
        for entry in parsed.entries:
            items.append(NewsItem(
                source=source_name,
                title=getattr(entry, "title", "").strip(),
                summary=getattr(entry, "summary", getattr(entry, "description", "")).strip(),
                link=getattr(entry, "link", ""),
                published=getattr(entry, "published", getattr(entry, "updated", "")),
            ))
    except Exception as exc:
        log.error("Error fetching %s: %s", source_name, exc)
    return items


def fetch_all_news(feeds: dict[str, str] | None = None, delay: float = 0.5) -> List[NewsItem]:
    """Fetch and combine headlines from every configured RSS feed."""
    feeds = feeds or RSS_FEEDS
    all_items: List[NewsItem] = []
    for name, url in feeds.items():
        items = fetch_feed(name, url)
        log.info("%s: %d headlines", name, len(items))
        all_items.extend(items)
        if len(all_items) >= MAX_HEADLINES_PER_RUN:
            break
        time.sleep(delay)  # be polite to free endpoints

    # de-duplicate by title (different feeds often carry the same wire story)
    seen = set()
    deduped = []
    for item in all_items:
        key = item.title.lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped[:MAX_HEADLINES_PER_RUN]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    news = fetch_all_news()
    print(f"Fetched {len(news)} unique headlines")
    for n in news[:5]:
        print("-", n.source, "|", n.title)
