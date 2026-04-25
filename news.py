import asyncio
import logging
from datetime import datetime
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from parser import NewsParser

logger = logging.getLogger(__name__)


class NewsScraper:
    """
    Official macro / Forex news sources only.

    Active sources:
    - Fed
    - BLS
    - BEA
    - ECB
    - Eurostat
    - BoE
    - ONS
    - BoJ

    Removed from active fetching:
    - CNBC
    - Bloomberg
    - Fox Business
    - CNBC Europe
    - CNBC Asia
    - Bloomberg Quicktake
    - Iraq Business News
    - ForexFactory calendar

    No keyword filtering is used here.
    Any item found from these official sources is returned.
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

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; OfficialForexNewsBot/1.0; "
                "+https://t.me/your_channel)"
            )
        }
        self.parser = NewsParser()

    def _parse_atom_entry(
        self,
        entry,
        source_name: str,
        category: str,
        currency: str,
    ) -> dict:
        title_tag = entry.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        summary_tag = entry.find("summary") or entry.find("content")
        summary = ""
        if summary_tag:
            summary = self.parser._clean_summary(
                summary_tag.get_text(" ", strip=True)
            )

        link_tag = entry.find("link")
        url = ""
        if link_tag:
            url = link_tag.get("href") or link_tag.get_text(strip=True)

        published_tag = entry.find("published") or entry.find("updated")
        published_at = (
            published_tag.get_text(strip=True)
            if published_tag
            else datetime.now().isoformat()
        )

        return {
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

    def _parse_html_articles(
        self,
        html: str,
        base_url: str,
        source_name: str,
        category: str,
        currency: str,
    ) -> list:
        """
        HTML fallback for official pages that do not expose a simple RSS feed.

        No keyword filter is used.
        It extracts links from the official page and returns them as articles.
        """
        soup = BeautifulSoup(html, "html.parser")
        articles = []
        seen_titles = set()

        for link in soup.find_all("a", href=True):
            title = link.get_text(" ", strip=True)

            if not title or len(title) < 8:
                continue

            title_key = title.lower()
            if title_key in seen_titles:
                continue

            url = urljoin(base_url, link["href"])
            seen_titles.add(title_key)

            articles.append(
                {
                    "title": title,
                    "summary": "",
                    "url": url,
                    "source": source_name,
                    "category": category,
                    "currency": currency,
                    "pairs": self.parser.detect_pairs(title),
                    "image_url": None,
                    "published_at": datetime.now().isoformat(),
                }
            )

            if len(articles) >= 10:
                break

        return articles

    async def fetch_url(
        self,
        session,
        source_name: str,
        source_info: dict,
        url: str,
    ) -> list:
        articles = []
        category = source_info["category"]
        currency = source_info["currency"]

        try:
            async with session.get(url, timeout=20) as resp:
                if resp.status != 200:
                    logger.warning(
                        f"{source_name} returned HTTP {resp.status}: {url}"
                    )
                    return articles

                text = await resp.text()
                soup = BeautifulSoup(text, "xml")

                items = soup.find_all("item")
                entries = soup.find_all("entry")

                if items:
                    for item in items[:20]:
                        article = self.parser.parse_rss_item(
                            item=item,
                            source_name=source_name,
                            category=category,
                        )
                        article["currency"] = currency
                        articles.append(article)

                    return articles

                if entries:
                    for entry in entries[:20]:
                        article = self._parse_atom_entry(
                            entry=entry,
                            source_name=source_name,
                            category=category,
                            currency=currency,
                        )
                        articles.append(article)

                    return articles

                return self._parse_html_articles(
                    html=text,
                    base_url=url,
                    source_name=source_name,
                    category=category,
                    currency=currency,
                )

        except Exception as e:
            logger.error(f"Error fetching {source_name} from {url}: {e}")
            return articles

    async def fetch_source(
        self,
        session,
        source_name: str,
        source_info: dict,
    ) -> list:
        tasks = [
            self.fetch_url(
                session=session,
                source_name=source_name,
                source_info=source_info,
                url=url,
            )
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
                self.fetch_source(
                    session=session,
                    source_name=name,
                    source_info=info,
                )
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

        return all_articles
