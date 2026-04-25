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

    Old public-news RSS sources such as CNBC, Bloomberg, Fox Business,
    CNBC Europe, CNBC Asia, Bloomberg Quicktake, and Iraq Business News
    have been removed from active fetching.
    """

    OFFICIAL_SOURCES = {
        "Fed": {
            "category": "official_usd",
            "currency": "USD",
            "urls": [
                # Federal Reserve Board official RSS: press releases.
                "https://www.federalreserve.gov/feeds/press_all.xml",
            ],
        },
        "BLS": {
            "category": "official_usd",
            "currency": "USD",
            "urls": [
                # Bureau of Labor Statistics official RSS feeds.
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
                # BEA official current releases page. Parsed as HTML fallback.
                "https://www.bea.gov/news/current-releases",
            ],
        },
        "ECB": {
            "category": "official_eur",
            "currency": "EUR",
            "urls": [
                # European Central Bank official RSS feeds.
                "https://www.ecb.europa.eu/rss/press.html",
                "https://www.ecb.europa.eu/rss/statpress.html",
            ],
        },
        "Eurostat": {
            "category": "official_eur",
            "currency": "EUR",
            "urls": [
                # Eurostat official Euro indicators page. Parsed as HTML fallback.
                "https://ec.europa.eu/eurostat/web/euro-indicators",
            ],
        },
        "BoE": {
            "category": "official_gbp",
            "currency": "GBP",
            "urls": [
                # Bank of England official RSS feeds.
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
                # ONS official release calendar. The RSS parameter returns the RSS view.
                "https://www.ons.gov.uk/releasecalendar?rss",
            ],
        },
        "BoJ": {
            "category": "official_jpy",
            "currency": "JPY",
            "urls": [
                # Bank of Japan official RSS.
                "https://www.boj.or.jp/en/rss/whatsnew.xml",
            ],
        },
    }

    # Hard rule-based filter so the bot stays macro/Forex-only before AI.
    IMPORTANT_KEYWORDS = [
        "interest rate",
        "rate decision",
        "policy rate",
        "monetary policy",
        "fomc",
        "federal funds rate",
        "bank rate",
        "mpc",
        "governing council",
        "cpi",
        "consumer price index",
        "inflation",
        "ppi",
        "producer price index",
        "pce",
        "personal income",
        "personal spending",
        "personal consumption expenditures",
        "employment situation",
        "nonfarm payroll",
        "non-farm payroll",
        "payrolls",
        "unemployment",
        "labor market",
        "labour market",
        "wages",
        "earnings",
        "gdp",
        "gross domestic product",
        "retail sales",
        "industrial production",
        "pmi",
        "trade balance",
        "international trade",
        "outlook report",
        "summary of opinions",
        "economic projections",
        "press conference",
        "speech",
        "testimony",
        "powell",
        "lagarde",
        "bailey",
        "ueda",
    ]

    BLOCKED_KEYWORDS = [
        "crypto",
        "bitcoin",
        "ethereum",
        "stock split",
        "earnings call",
        "company earnings",
        "merger",
        "acquisition",
        "lawsuit",
        "football",
        "sport",
    ]

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; OfficialForexNewsBot/1.0; "
                "+https://t.me/your_channel)"
            )
        }
        self.parser = NewsParser()

    def _is_relevant(self, title: str, summary: str = "") -> bool:
        text = f"{title} {summary}".lower()

        if any(word in text for word in self.BLOCKED_KEYWORDS):
            return False

        return any(word in text for word in self.IMPORTANT_KEYWORDS)

    def _parse_atom_entry(self, entry, source_name: str, category: str, currency: str):
        title = entry.find("title").get_text(strip=True) if entry.find("title") else ""

        summary_tag = entry.find("summary") or entry.find("content")
        summary = self.parser._clean_summary(summary_tag.get_text(" ", strip=True)) if summary_tag else ""

        link_tag = entry.find("link")
        url = ""
        if link_tag:
            url = link_tag.get("href") or link_tag.get_text(strip=True)

        published_tag = entry.find("published") or entry.find("updated")
        published_at = published_tag.get_text(strip=True) if published_tag else datetime.now().isoformat()

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

    def _parse_html_articles(self, html: str, base_url: str, source_name: str, category: str, currency: str):
        """
        Fallback for official pages that do not expose a simple RSS feed.
        It extracts relevant official-release links only.
        """
        soup = BeautifulSoup(html, "html.parser")
        articles = []
        seen_titles = set()

        for link in soup.find_all("a", href=True):
            title = link.get_text(" ", strip=True)
            if not title or len(title) < 8:
                continue

            if title.lower() in seen_titles:
                continue

            if not self._is_relevant(title):
                continue

            url = urljoin(base_url, link["href"])
            seen_titles.add(title.lower())

            articles.append({
                "title": title,
                "summary": "",
                "url": url,
                "source": source_name,
                "category": category,
                "currency": currency,
                "pairs": self.parser.detect_pairs(title),
                "image_url": None,
                "published_at": datetime.now().isoformat(),
            })

            if len(articles) >= 10:
                break

        return articles

    async def fetch_url(self, session, source_name: str, source_info: dict, url: str):
        articles = []
        category = source_info["category"]
        currency = source_info["currency"]

        try:
            async with session.get(url, timeout=20) as resp:
                if resp.status != 200:
                    logger.warning(f"{source_name} returned HTTP {resp.status}: {url}")
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

                        if self._is_relevant(article.get("title", ""), article.get("summary", "")):
                            articles.append(article)

                    return articles

                if entries:
                    for entry in entries[:20]:
                        article = self._parse_atom_entry(entry, source_name, category, currency)

                        if self._is_relevant(article.get("title", ""), article.get("summary", "")):
                            articles.append(article)

                    return articles

                # HTML fallback for pages such as BEA current releases / Eurostat indicators.
                return self._parse_html_articles(text, url, source_name, category, currency)

        except Exception as e:
            logger.error(f"Error fetching {source_name} from {url}: {e}")
            return articles

    async def fetch_source(self, session, source_name: str, source_info: dict):
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

    async def fetch_all(self):
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
                title = (article.get("title") or "").strip().lower()

                if not url and not title:
                    continue

                dedupe_key = url or title
                if dedupe_key in seen_urls or title in seen_titles:
                    continue

                seen_urls.add(dedupe_key)
                if title:
                    seen_titles.add(title)

                all_articles.append(article)

        return all_articles
