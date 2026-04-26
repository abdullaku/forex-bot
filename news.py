import asyncio
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from parser import NewsParser

logger = logging.getLogger(__name__)


class NewsScraper:
    """
    Official macro / Forex news scraper.

    Active sources only:
    - Fed
    - BLS
    - BEA
    - ECB
    - Eurostat
    - BoE
    - ONS
    - BoJ

    Important:
    - No AI filtering here.
    - No time limit.
    - No post/count limit.
    - No per-feed item limit.
    - The bot decides by event type, not by a fixed number of posts.
    - Deduplication is still used so the same URL/title is not posted twice.
    """

    OFFICIAL_SOURCES = {
        "Fed": {
            "category": "official_usd",
            "currency": "USD",
            "urls": [
                "https://www.federalreserve.gov/feeds/press_all.xml",
            ],
        },
        "BLS": {
            "category": "official_usd",
            "currency": "USD",
            "urls": [
                "https://www.bls.gov/feed/bls_latest.rss",
                "https://www.bls.gov/feed/empsit.rss",
                "https://www.bls.gov/feed/cpi.rss",
                "https://www.bls.gov/feed/ppi.rss",
                "https://www.bls.gov/feed/cpi_latest.rss",
                "https://www.bls.gov/feed/ppi_latest.rss",
            ],
        },
        "BEA": {
            "category": "official_usd",
            "currency": "USD",
            "urls": [
                "https://www.bea.gov/news/current-releases",
            ],
        },
        "ECB": {
            "category": "official_eur",
            "currency": "EUR",
            "urls": [
                "https://www.ecb.europa.eu/rss/press.html",
                "https://www.ecb.europa.eu/rss/statpress.html",
            ],
        },
        "Eurostat": {
            "category": "official_eur",
            "currency": "EUR",
            "urls": [
                "https://ec.europa.eu/eurostat/web/euro-indicators",
            ],
        },
        "BoE": {
            "category": "official_gbp",
            "currency": "GBP",
            "urls": [
                "https://www.bankofengland.co.uk/rss/news",
                "https://www.bankofengland.co.uk/rss/speeches",
                "https://www.bankofengland.co.uk/rss/publications",
                "https://www.bankofengland.co.uk/rss/statistics",
            ],
        },
        "ONS": {
            "category": "official_gbp",
            "currency": "GBP",
            "urls": [
                "https://www.ons.gov.uk/releasecalendar?rss",
            ],
        },
        "BoJ": {
            "category": "official_jpy",
            "currency": "JPY",
            "urls": [
                "https://www.boj.or.jp/en/rss/whatsnew.xml",
            ],
        },
    }

    EVENT_TYPES = {
        "inflation": [
            "cpi",
            "consumer price index",
            "inflation",
            "ppi",
            "producer price index",
            "pce",
            "personal consumption expenditures",
            "deflator",
        ],
        "jobs": [
            "employment situation",
            "nonfarm payroll",
            "non-farm payroll",
            "nfp",
            "payrolls",
            "unemployment",
            "jobless",
            "labor market",
            "labour market",
            "wages",
            "earnings",
            "average hourly earnings",
            "industry, trade and services",
            "labour costs",
            "labor costs",
            "employment",
            "jobs report",
        ],
        "growth": [
            "gdp",
            "gross domestic product",
            "retail sales",
            "industrial production",
            "trade balance",
            "international trade",
            "pmi",
            "manufacturing",
            "services",
            # BEA
            "personal income",
            "personal consumption",
            "state and local",
            "corporate profits",
            "county",
            # Eurostat
            "government deficit",
            "government debt",
            "euro area",
            "seasonally adjusted",
            "exchange and interest rates",
            "exchange rates",
            "current account",
            "balance of payments",
            "industrial output",
            "construction output",
            "business cycle",
        ],
        "central_bank": [
            "interest rate",
            "rate decision",
            "policy rate",
            "bank rate",
            "cash rate",
            "federal funds rate",
            "monetary policy",
            "fomc",
            "mpc",
            "governing council",
            "press conference",
            "economic projections",
            "summary of economic projections",
            "outlook report",
            "summary of opinions",
        ],
        "key_speech": [
            "powell",
            "lagarde",
            "bailey",
            "ueda",
        ],
    }

    BLOCKED_KEYWORDS = [
        "supervision",
        "regulation",
        "regulatory",
        "community bank",
        "consumer compliance",
        "enforcement action",
        "working paper",
        "research paper",
        "staff paper",
        "conference",
        "webinar",
        "museum",
        "holiday",
        "appointment",
        "vacancy",
        "procurement",
        "consultation",
        "taxonomy",
        "user guide",
        "newsletter",
        "podcast",
        "blog",
        "education",
    ]

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; OfficialForexNewsBot/1.0; "
                "+https://t.me/your_channel)"
            )
        }
        self.parser = NewsParser()
        self._feed_cache: dict = {}  # url -> {"etag": ..., "last_modified": ...}

    def _clean_title(self, title: str) -> str:
        return re.sub(r"\s+", " ", title or "").strip()

    def _parse_date(self, value: str):
        if not value:
            return None

        value = value.strip()

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
            return None

    def _classify_event(self, title: str, summary: str = "") -> str:
        text = f"{title} {summary}".lower()

        for event_type, keywords in self.EVENT_TYPES.items():
            if any(keyword in text for keyword in keywords):
                return event_type

        return "other"

    def _is_macro_relevant(self, title: str, summary: str = "") -> bool:
        text = f"{title} {summary}".lower()

        if any(blocked in text for blocked in self.BLOCKED_KEYWORDS):
            return False

        return self._classify_event(title, summary) != "other"

    def _source_priority(self, source: str) -> int:
        priorities = {
            "BLS": 100,
            "Fed": 95,
            "BEA": 90,
            "ECB": 85,
            "BoE": 80,
            "ONS": 75,
            "Eurostat": 70,
            "BoJ": 65,
        }
        return priorities.get(source, 0)

    def _article_sort_key(self, article: dict):
        parsed = self._parse_date(article.get("published_at", ""))
        if parsed is None:
            parsed = datetime.min.replace(tzinfo=timezone.utc)

        return (parsed, self._source_priority(article.get("source", "")))

    def _attach_event_type(self, article: dict) -> dict:
        article["event_type"] = self._classify_event(
            article.get("title", ""),
            article.get("summary", ""),
        )
        return article

    def _parse_atom_entry(self, entry, source_name: str, category: str, currency: str) -> dict:
        title_tag = entry.find("title")
        title = self._clean_title(title_tag.get_text(strip=True) if title_tag else "")

        summary_tag = entry.find("summary") or entry.find("content")
        summary = ""
        if summary_tag:
            summary = self.parser._clean_summary(summary_tag.get_text(" ", strip=True))

        link_tag = entry.find("link")
        url = ""
        if link_tag:
            url = link_tag.get("href") or link_tag.get_text(strip=True)

        published_tag = entry.find("published") or entry.find("updated")
        published_at = (
            published_tag.get_text(strip=True)
            if published_tag
            else datetime.now(timezone.utc).isoformat()
        )

        article = {
            "title": title,
            "summary": summary[:500],
            "url": url,
            "source": source_name,
            "category": category,
            "currency": currency,
            "pairs": self.parser.detect_pairs(title + " " + summary),
            "image_url": None,
            "published_at": published_at,
        }

        return self._attach_event_type(article)

    def _parse_html_articles(
        self,
        html: str,
        base_url: str,
        source_name: str,
        category: str,
        currency: str,
    ) -> list:
        """
        Strict fallback for official pages that are not simple RSS feeds.
        No count/time limit is used, but navigation/menu links are blocked.
        """
        soup = BeautifulSoup(html, "html.parser")
        articles = []
        seen_titles = set()

        for link in soup.find_all("a", href=True):
            title = self._clean_title(link.get_text(" ", strip=True))
            if not title or len(title) < 12:
                continue

            title_key = title.lower()
            if title_key in seen_titles:
                continue

            url = urljoin(base_url, link["href"])

            if not self._is_macro_relevant(title):
                continue

            if source_name == "BEA" and "/news/" not in url and "/data/" not in url:
                continue

            if source_name == "Eurostat" and "euro-indicators" not in url and "products-euro-indicators" not in url:
                continue

            seen_titles.add(title_key)

            article = {
                "title": title,
                "summary": "",
                "url": url,
                "source": source_name,
                "category": category,
                "currency": currency,
                "pairs": self.parser.detect_pairs(title),
                "image_url": None,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }

            articles.append(self._attach_event_type(article))

        return articles

    async def fetch_url(self, session, source_name: str, source_info: dict, url: str) -> list:
        articles = []
        category = source_info["category"]
        currency = source_info["currency"]

        # ETag / Last-Modified هێڵەکان زیاد بکە
        cached = self._feed_cache.get(url, {})
        req_headers = {}
        if cached.get("etag"):
            req_headers["If-None-Match"] = cached["etag"]
        elif cached.get("last_modified"):
            req_headers["If-Modified-Since"] = cached["last_modified"]

        try:
            async with session.get(url, timeout=20, headers=req_headers) as resp:

                # 304 = هیچ نوێیەک نییە، زوو تێپەڕ بکە
                if resp.status == 304:
                    logger.debug(f"{source_name} not modified: {url}")
                    return articles

                if resp.status != 200:
                    logger.warning(f"{source_name} returned HTTP {resp.status}: {url}")
                    return articles

                # ETag / Last-Modified ذەخیرە بکە بۆ جاری داهاتوو
                new_cache = {}
                if resp.headers.get("ETag"):
                    new_cache["etag"] = resp.headers["ETag"]
                if resp.headers.get("Last-Modified"):
                    new_cache["last_modified"] = resp.headers["Last-Modified"]
                if new_cache:
                    self._feed_cache[url] = new_cache

                text = await resp.text()
                soup = BeautifulSoup(text, "xml")
                items = soup.find_all("item")
                entries = soup.find_all("entry")

                if items:
                    for item in items:
                        article = self.parser.parse_rss_item(
                            item=item,
                            source_name=source_name,
                            category=category,
                        )
                        article["currency"] = currency
                        article = self._attach_event_type(article)

                        if not self._is_macro_relevant(
                            article.get("title", ""),
                            article.get("summary", ""),
                        ):
                            continue

                        articles.append(article)

                    return articles

                if entries:
                    for entry in entries:
                        article = self._parse_atom_entry(
                            entry=entry,
                            source_name=source_name,
                            category=category,
                            currency=currency,
                        )

                        if not self._is_macro_relevant(
                            article.get("title", ""),
                            article.get("summary", ""),
                        ):
                            continue

                        articles.append(article)

                    return articles

                return self._parse_html_articles(
                    html=text,
                    base_url=url,
                    source_name=source_name,
                    category=category,
                    currency=currency,
                )

        except Exception as exc:
            logger.error(f"Error fetching {source_name} from {url}: {exc}")
            return articles

    async def fetch_source(self, session, source_name: str, source_info: dict) -> list:
        tasks = [
            self.fetch_url(session, source_name, source_info, url)
            for url in source_info["urls"]
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        articles = []
        for result in results:
            if isinstance(result, list):
                articles.extend(result)

        return articles

    async def fetch_all(self) -> list:
        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = [
                self.fetch_source(session, source_name=name, source_info=info)
                for name, info in self.OFFICIAL_SOURCES.items()
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        seen_urls = set()
        seen_titles = set()

        for result in results:
            if not isinstance(result, list):
                continue

            for article in result:
                url = (article.get("url") or "").split("?")[0].strip()
                title = (article.get("title") or "").strip()
                title_key = title.lower()

                if not url and not title:
                    continue

                dedupe_key = url or title_key

                if dedupe_key in seen_urls or title_key in seen_titles:
                    continue

                seen_urls.add(dedupe_key)

                if title_key:
                    seen_titles.add(title_key)

                all_articles.append(article)

        all_articles.sort(key=self._article_sort_key, reverse=True)
        return all_articles
