import asyncio
import logging

import aiohttp
from bs4 import BeautifulSoup

from parser import NewsParser

logger = logging.getLogger(__name__)


class NewsScraper:
    RSS_FEEDS = {
        "CNBC": {"url": "https://www.cnbc.com/id/10000311/device/rss/rss.html", "category": "global_markets"},
        "Bloomberg": {"url": "https://www.bloomberg.com/feeds/bview/rss.xml", "category": "analysis"},
        "Fox Business": {"url": "https://moxie.foxbusiness.com/google-publisher/markets.xml", "category": "us_markets"},
        "CNBC Europe": {"url": "https://www.cnbc.com/id/19793763/device/rss/rss.html", "category": "europe_forex"},
        "CNBC Asia": {"url": "https://www.cnbc.com/id/19832390/device/rss/rss.html", "category": "asia_forex"},
        "Bloomberg Quicktake": {"url": "https://feeds.bloomberg.com/markets/news.rss", "category": "economic_news"},
        "Iraq Business News": {"url": "https://www.iraq-businessnews.com/feed", "category": "iraq_economy"},
    }

    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self.parser = NewsParser()

    async def fetch_rss(self, source_name, feed_info):
        articles = []

        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(feed_info["url"], timeout=15) as resp:
                    if resp.status != 200:
                        return articles

                    soup = BeautifulSoup(await resp.text(), "xml")

                    for item in soup.find_all("item")[:10]:
                        article = self.parser.parse_rss_item(
                            item=item,
                            source_name=source_name,
                            category=feed_info["category"],
                        )
                        articles.append(article)

        except Exception as e:
            logger.error(f"Error {source_name}: {e}")

        return articles

    async def fetch_all(self):
        tasks = [
            self.fetch_rss(source_name=name, feed_info=info)
            for name, info in self.RSS_FEEDS.items()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        seen_urls = set()

        for result in results:
            if not isinstance(result, list):
                continue

            for article in result:
                clean_url = article["url"].split("?")[0]

                if clean_url in seen_urls:
                    continue

                seen_urls.add(clean_url)
                all_articles.append(article)

        return all_articles
