import asyncio
import aiohttp
import feedparser
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from config import Config

logger = logging.getLogger(__name__)

class NewsScraper:
    RSS_FEEDS = {
        "FXStreet": {"url": "https://www.fxstreet.com/rss", "category": "technical_analysis"},
        "DailyFX": {"url": "https://www.dailyfx.com/feeds/all", "category": "forex_signal"},
        "Reuters": {"url": "https://feeds.reuters.com/reuters/businessNews", "category": "economic_news"},
        "MarketWatch": {"url": "https://feeds.marketwatch.com/marketwatch/topstories/", "category": "economic_news"},
        "Investing": {"url": "https://www.investing.com/rss/news.rss", "category": "economic_news"},
    }
    FOREX_PAIRS = ["EUR/USD","GBP/USD","USD/JPY","USD/CHF","AUD/USD","USD/CAD","XAU/USD","GOLD","WTI"]
    PRIORITY_KEYWORDS = ["CPI","NFP","GDP","interest rate","Federal Reserve","Fed","ECB","inflation","FOMC"]

    def detect_pairs(self, text):
        return [p for p in self.FOREX_PAIRS if p.upper() in text.upper()]

    def is_forex_relevant(self, title, summary):
        text = (title + " " + summary).lower()
        keywords = ["forex","currency","dollar","euro","pound","yen","gold","oil","inflation","interest rate","fed","ecb","cpi","nfp","gdp","trading","market","bullish","bearish"]
        return any(k in text for k in keywords)

    def is_priority(self, title, summary):
        text = (title + " " + summary).upper()
        return any(k.upper() in text for k in self.PRIORITY_KEYWORDS)

    async def fetch_rss(self, source_name, feed_info):
        articles = []
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:8]:
                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                url = entry.get("link", "")
                if summary:
                    soup = BeautifulSoup(summary, "html.parser")
                    summary = soup.get_text(separator=" ").strip()
                if not self.is_forex_relevant(title, summary):
                    continue
                articles.append({
                    "title": title, "summary": summary[:500] if summary else title,
                    "url": url, "source": source_name, "category": feed_info["category"],
                    "pairs": self.detect_pairs(title + " " + summary),
                    "is_priority": self.is_priority(title, summary),
                    "published": entry.get("published", datetime.now().isoformat()),
                    "title_ku": "", "summary_ku": "", "signal": None
                })
        except Exception as e:
            logger.error(f"Error fetching {source_name}: {e}")
        return articles

    async def fetch_all(self):
        tasks = [self.fetch_rss(name, info) for name, info in self.RSS_FEEDS.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_articles = []
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
        logger.info(f"Fetched {len(all_articles)} articles")
        return all_articles
