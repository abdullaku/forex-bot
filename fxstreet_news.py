import asyncio
import json
import logging
import re
from datetime import datetime, timezone, timedelta, time as dtime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

from parser import NewsParser

logger = logging.getLogger(__name__)


class FXStreetNewsService:
    """
    FXStreet market-news source.

    This is intentionally separate from official macro news.

    Rules:
      - No posts during quiet hours: 00:00-06:00 Baghdad time.
      - News is scored by relevance/strength.
      - Strong breaking news can be posted immediately outside quiet hours.
      - Normal strong news is queued, then the strongest item is released every 30 minutes.
      - No hard daily post limit, so strong news is not missed.
      - Topic cooldown prevents repeated posts about the same pair/topic.
      - Images are kept when the RSS feed provides them.
      - Queue is saved to state file so restart/redeploy does not lose strong queued news.
    """

    BAGHDAD_TZ = timezone(timedelta(hours=3))

    DEFAULT_FEEDS = [
        "https://www.fxstreet.com/rss/news",
    ]

    STRONG_KEYWORDS = {
        "fed": 4,
        "federal reserve": 4,
        "powell": 4,
        "fomc": 4,
        "ecb": 4,
        "lagarde": 4,
        "boe": 4,
        "bank of england": 4,
        "boj": 4,
        "bank of japan": 4,
        "ueda": 4,
        "rate decision": 4,
        "interest rate": 4,
        "rate cut": 4,
        "rate hike": 4,
        "monetary policy": 4,
        "cpi": 3,
        "inflation": 3,
        "nfp": 3,
        "nonfarm payroll": 3,
        "jobs": 3,
        "employment": 3,
        "unemployment": 3,
        "yields": 3,
        "bond yields": 3,
        "treasury yields": 3,
        "risk sentiment": 2,
        "risk appetite": 2,
        "risk aversion": 2,
        "gold": 2,
        "xau/usd": 3,
        "oil": 2,
        "wti": 2,
        "brent": 2,
        "dxy": 3,
        "us dollar index": 3,
        "us dollar": 3,
        "dollar": 2,
    }

    PAIR_KEYWORDS = {
        "eur/usd": 4,
        "gbp/usd": 4,
        "usd/jpy": 4,
        "usd/cad": 4,
        "aud/usd": 4,
        "usd/chf": 4,
        "nzd/usd": 3,
        "eur/jpy": 3,
        "gbp/jpy": 3,
    }

    CURRENCY_KEYWORDS = {
        "usd": 2,
        "eur": 2,
        "gbp": 2,
        "jpy": 2,
        "cad": 1,
        "aud": 1,
        "chf": 1,
        "nzd": 1,
    }

    BLOCKED_KEYWORDS = [
        "technical analysis",
        "price forecast",
        "forecast:",
        "weekly forecast",
        "monthly forecast",
        "elliott wave",
        "support and resistance",
        "bullish pattern",
        "bearish pattern",
        "crypto",
        "bitcoin",
        "ethereum",
        "ripple",
        "xrp",
        "stocks",
        "stock market",
        "equities",
        "shares",
        "broker",
        "buy signal",
        "sell signal",
        "trading signal",
        "signals",
        "best brokers",
        "sponsored",
    ]

    BREAKING_HINTS = [
        "breaking",
        "surprise",
        "unexpected",
        "hawkish",
        "dovish",
        "soars",
        "surges",
        "jumps",
        "plunges",
        "drops sharply",
        "slumps",
        "after fed",
        "after ecb",
        "after boj",
        "after boe",
        "after cpi",
        "after nfp",
        "rate decision",
    ]

    def __init__(self):
        # Hardcoded settings. No Koyeb FXStreet variables are required.
        self.enabled = True
        self.check_interval_minutes = 15
        self.min_score = 6
        self.breaking_score = 10
        self.queue_release_minutes = 30
        self.topic_cooldown_minutes = 120
        self.quiet_start = self._parse_clock("00:00")
        self.quiet_end = self._parse_clock("06:00")
        self.send_images = True

        self.state_path = Path(".fxstreet_state.json")
        self.feeds = self.DEFAULT_FEEDS[:]

        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; KurdTraderBot/1.0; +https://t.me/KurdTraderKRD)",
            "Accept": "application/rss+xml,application/xml,text/xml,text/html,*/*",
        }

        self.parser = NewsParser()
        self._feed_cache: dict = {}
        self._last_fetch_at: Optional[datetime] = None
        self._last_release_at: Optional[datetime] = None
        self._queue: list[dict] = []
        self._seen_urls: set[str] = set()
        self._topic_last_posted: dict[str, str] = {}
        self._load_state()

    def _now(self) -> datetime:
        return datetime.now(self.BAGHDAD_TZ)

    def _parse_clock(self, value: str) -> dtime:
        try:
            hour, minute = value.strip().split(":", 1)
            return dtime(int(hour), int(minute), tzinfo=self.BAGHDAD_TZ)
        except Exception:
            return dtime(0, 0, tzinfo=self.BAGHDAD_TZ)

    def _load_state(self) -> None:
        try:
            if not self.state_path.exists():
                return

            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._seen_urls = set(data.get("seen_urls", []))
            self._topic_last_posted = dict(data.get("topic_last_posted", {}))
            self._queue = list(data.get("queue", []))

        except Exception as e:
            logger.warning("FXStreet state could not be loaded: %s", e)

    def _save_state(self) -> None:
        try:
            seen = list(self._seen_urls)[-500:]
            queue = self._queue[-30:]

            data = {
                "seen_urls": seen,
                "topic_last_posted": self._topic_last_posted,
                "queue": queue,
            }

            self.state_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        except Exception as e:
            logger.warning("FXStreet state could not be saved: %s", e)

    def _in_quiet_hours(self, now: datetime) -> bool:
        t = now.timetz()
        start = self.quiet_start
        end = self.quiet_end

        if start <= end:
            return start <= t < end

        return t >= start or t < end

    def _fetch_due(self, now: datetime) -> bool:
        if self._last_fetch_at is None:
            return True

        return (now - self._last_fetch_at).total_seconds() >= self.check_interval_minutes * 60

    def _release_due(self, now: datetime) -> bool:
        if self._last_release_at is None:
            return True

        return (now - self._last_release_at).total_seconds() >= self.queue_release_minutes * 60

    def _clean_text(self, value: str) -> str:
        value = re.sub(r"<[^>]+>", " ", value or "")
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _parse_date(self, value: str) -> datetime:
        if not value:
            return datetime.now(timezone.utc)

        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            pass

        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)

    def _canonical_url(self, url: str) -> str:
        if not url:
            return ""

        parsed = urlparse(url.strip())
        return parsed._replace(query="", fragment="").geturl()

    def _extract_image_url(self, item) -> str:
        media = item.find("media:content")
        if media and media.get("url"):
            return media["url"]

        thumb = item.find("media:thumbnail")
        if thumb and thumb.get("url"):
            return thumb["url"]

        enclosure = item.find("enclosure")
        if enclosure and enclosure.get("type", "").lower().startswith("image"):
            return enclosure.get("url", "")

        desc = item.find("description") or item.find("content:encoded")
        if desc:
            match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(desc))
            if match:
                return match.group(1)

        return ""

    def _topic_key(self, text: str) -> str:
        lower = text.lower()

        for pair in self.PAIR_KEYWORDS:
            if pair in lower:
                return pair.upper()

        for key in (
            "fed",
            "ecb",
            "boe",
            "boj",
            "cpi",
            "inflation",
            "nfp",
            "gold",
            "oil",
            "yields",
            "dxy",
        ):
            if key in lower:
                return key.upper()

        for cur in self.CURRENCY_KEYWORDS:
            if re.search(rf"\b{re.escape(cur)}\b", lower):
                return cur.upper()

        title_words = re.findall(r"[a-zA-Z]{4,}", lower)
        return " ".join(title_words[:3]) or "FXSTREET"

    def _score_article(self, title: str, summary: str) -> tuple[int, list[str]]:
        text = f"{title} {summary}".lower()
        reasons = []
        score = 0

        if any(blocked in text for blocked in self.BLOCKED_KEYWORDS):
            return -10, ["blocked"]

        for keyword, points in self.PAIR_KEYWORDS.items():
            if keyword in text:
                score += points
                reasons.append(keyword.upper())

        for keyword, points in self.STRONG_KEYWORDS.items():
            if keyword in text:
                score += points
                reasons.append(keyword)

        for keyword, points in self.CURRENCY_KEYWORDS.items():
            if re.search(rf"\b{re.escape(keyword)}\b", text):
                score += points
                reasons.append(keyword.upper())

        if any(hint in text for hint in self.BREAKING_HINTS):
            score += 2
            reasons.append("breaking_hint")

        if len(title.strip()) < 18:
            score -= 2

        return score, reasons

    def _topic_in_cooldown(self, topic: str, now: datetime) -> bool:
        value = self._topic_last_posted.get(topic)
        if not value:
            return False

        try:
            last = datetime.fromisoformat(value)
            if last.tzinfo is None:
                last = last.replace(tzinfo=self.BAGHDAD_TZ)
        except Exception:
            return False

        return (now - last.astimezone(self.BAGHDAD_TZ)).total_seconds() < self.topic_cooldown_minutes * 60

    def _mark_topic_posted(self, topic: str, now: datetime) -> None:
        self._topic_last_posted[topic] = now.isoformat()
        self._save_state()

    def _parse_rss_item(self, item) -> Optional[dict]:
        title_tag = item.find("title")
        title = self._clean_text(title_tag.get_text(" ", strip=True) if title_tag else "")
        if not title:
            return None

        desc_tag = item.find("description") or item.find("content:encoded")
        summary = self._clean_text(desc_tag.get_text(" ", strip=True) if desc_tag else "")

        link_tag = item.find("link")
        url = self._canonical_url(link_tag.get_text(strip=True) if link_tag else "")
        if not url:
            guid = item.find("guid")
            url = self._canonical_url(guid.get_text(strip=True) if guid else "")

        if not url:
            return None

        pub_tag = item.find("pubDate") or item.find("published") or item.find("updated")
        published_at = pub_tag.get_text(strip=True) if pub_tag else datetime.now(timezone.utc).isoformat()

        score, reasons = self._score_article(title, summary)
        topic = self._topic_key(f"{title} {summary}")

        if score < self.min_score:
            return None

        return {
            "title": title,
            "summary": summary[:500],
            "url": url,
            "source": "FXStreet",
            "category": "forex_market_news",
            "currency": "FX",
            "pairs": self.parser.detect_pairs(title + " " + summary),
            "image_url": self._extract_image_url(item) if self.send_images else None,
            "published_at": self._parse_date(published_at).isoformat(),
            "event_type": "forex_market_news",
            "score": score,
            "score_reasons": reasons,
            "topic_key": topic,
        }

    async def _fetch_feed(self, session: aiohttp.ClientSession, feed_url: str) -> list[dict]:
        articles: list[dict] = []
        cached = self._feed_cache.get(feed_url, {})
        req_headers = {}

        if cached.get("etag"):
            req_headers["If-None-Match"] = cached["etag"]
        elif cached.get("last_modified"):
            req_headers["If-Modified-Since"] = cached["last_modified"]

        try:
            async with session.get(feed_url, headers=req_headers, timeout=20) as resp:
                if resp.status == 304:
                    return []

                if resp.status != 200:
                    logger.warning("FXStreet returned HTTP %s: %s", resp.status, feed_url)
                    return []

                new_cache = {}
                if resp.headers.get("ETag"):
                    new_cache["etag"] = resp.headers["ETag"]
                if resp.headers.get("Last-Modified"):
                    new_cache["last_modified"] = resp.headers["Last-Modified"]
                if new_cache:
                    self._feed_cache[feed_url] = new_cache

                text = await resp.text()

            soup = BeautifulSoup(text, "xml")

            for item in soup.find_all("item"):
                article = self._parse_rss_item(item)
                if article:
                    articles.append(article)

        except Exception as e:
            logger.error("FXStreet fetch error: %s", e)

        return articles

    async def _fetch_new_articles(self, now: datetime) -> list[dict]:
        async with aiohttp.ClientSession(headers=self.headers) as session:
            results = await asyncio.gather(
                *(self._fetch_feed(session, feed) for feed in self.feeds),
                return_exceptions=True,
            )

        articles: list[dict] = []

        for result in results:
            if isinstance(result, list):
                articles.extend(result)

        output: list[dict] = []

        for article in articles:
            url = article.get("url", "")

            if not url or url in self._seen_urls:
                continue

            published = self._parse_date(article.get("published_at", ""))
            if published < datetime.now(timezone.utc) - timedelta(hours=8):
                self._seen_urls.add(url)
                continue

            self._seen_urls.add(url)
            output.append(article)

        self._save_state()
        return output

    def _add_to_queue(self, articles: list[dict]) -> None:
        existing = {item.get("url") for item in self._queue}

        for article in articles:
            if article.get("url") in existing:
                continue

            self._queue.append(article)

        self._queue.sort(
            key=lambda x: (
                int(x.get("score", 0)),
                self._parse_date(x.get("published_at", "")),
            ),
            reverse=True,
        )

        self._queue = self._queue[:30]
        self._save_state()

    def _pick_best_from_queue(self, now: datetime) -> Optional[dict]:
        if not self._queue:
            return None

        remaining = []
        chosen = None

        for article in self._queue:
            topic = article.get("topic_key", "FXSTREET")

            if self._topic_in_cooldown(topic, now):
                remaining.append(article)
                continue

            if chosen is None:
                chosen = article
            else:
                remaining.append(article)

        self._queue = remaining
        self._save_state()
        return chosen

    async def fetch_all(self) -> list[dict]:
        if not self.enabled:
            return []

        now = self._now()

        if self._fetch_due(now):
            self._last_fetch_at = now

            new_articles = await self._fetch_new_articles(now)
            if new_articles:
                self._add_to_queue(new_articles)
                logger.info("FXStreet queued %s strong market-news items", len(new_articles))

        # Do not post during quiet hours.
        # Fetching still happens, so strong news is not missed.
        if self._in_quiet_hours(now):
            return []

        ready: list[dict] = []

        # Breaking/high-score items can be posted immediately outside quiet hours.
        for article in list(self._queue):
            topic = article.get("topic_key", "FXSTREET")

            if int(article.get("score", 0)) >= self.breaking_score and not self._topic_in_cooldown(topic, now):
                self._queue.remove(article)
                self._save_state()

                self._mark_topic_posted(topic, now)
                ready.append(article)

                logger.info(
                    "FXStreet breaking item selected: score=%s title=%s",
                    article.get("score"),
                    article.get("title", "")[:80],
                )

                return ready

        # Normal strong items are released from queue every 30 minutes.
        if self._release_due(now):
            chosen = self._pick_best_from_queue(now)
            self._last_release_at = now

            if chosen:
                topic = chosen.get("topic_key", "FXSTREET")
                self._mark_topic_posted(topic, now)
                ready.append(chosen)

                logger.info(
                    "FXStreet item selected: score=%s title=%s",
                    chosen.get("score"),
                    chosen.get("title", "")[:80],
                )

        return ready
