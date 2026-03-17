import asyncio
import aiohttp
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class NewsScraper:
    RSS_FEEDS = {
        "CNBC": {"url": "https://www.cnbc.com/id/10000664/device/rss/rss.html", "category": "economic_news"},
        "Bloomberg": {"url": "https://feeds.bloomberg.com/markets/news.rss", "category": "economic_news"},
        "Fox Business": {"url": "https://moxie.foxbusiness.com/google-publisher/markets.xml", "category": "economic_news"},
    }

    FOREX_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "GOLD", "WTI", "OIL", "USD"]

    PRIORITY_KEYWORDS = [
        "CPI", "NFP", "GDP", "Fed", "Federal Reserve", "ECB", "inflation",
        "interest rate", "FOMC", "recession", "tariff", "Bank of England",
        "central bank", "monetary policy", "gold", "oil", "crude"
    ]

    FOREX_KEYWORDS = [
        "forex", "currency", "dollar", "euro", "pound", "yen", "gold", "oil",
        "inflation", "interest rate", "fed", "ecb", "cpi", "nfp", "gdp",
        "market", "bullish", "bearish", "trade", "economy", "bank", "rate",
        "USD", "EUR", "GBP", "JPY", "central bank", "monetary", "crude",
        "treasury", "yield", "bond", "reserve", "Goldman", "JPMorgan",
        "Federal Reserve", "European Central Bank", "Bank of England",
        "surge", "fall", "volatility", "outlook", "forecast"
    ]

    def detect_pairs(self, text):
        return [p for p in self.FOREX_PAIRS if p.upper() in text.upper()]

    def is_forex_relevant(self, title, summary):
        text = (title + " " + summary).lower()
        return any(k.lower() in text for k in self.FOREX_KEYWORDS)

    async def fetch_rss(self, source_name, feed_info):
        articles = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(feed_info["url"], timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(text)
                        ns = {'atom': 'http://www.w3.org/2005/Atom'}
                        items = root.findall('.//item') or root.findall('.//atom:entry', ns)
                        for item in items[:5]:
                            title = (item.findtext('title') or item.findtext('atom:title', namespaces=ns) or "").strip()
                            summary = (item.findtext('description') or item.findtext('atom:summary', namespaces=ns) or "").strip()
                            url = (item.findtext('link') or item.findtext('atom:link', namespaces=ns) or "").strip()
                            if not self.is_forex_relevant(title, summary):
                                continue
                            articles.append({
                                "title": title, "summary": summary[:500],
                                "url": url, "source": source_name,
                                "category": feed_info["category"],
                                "pairs": self.detect_pairs(title + " " + summary),
                                "is_priority": any(k.upper() in (title + summary).upper() for k in self.PRIORITY_KEYWORDS),
                                "published": datetime.now().isoformat(),
                                "title_ku": "", "summary_ku": "", "signal": None
                            })
        except Exception as e:
            logger.error(f"Error fetching {source_name}: {e}")
        return articles

    async def fetch_all(self):
        tasks = [self.fetch_rss(name, info) for name, info in self.RSS_FEEDS.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_articles = []
        seen_urls = set()
        for result in results:
            if isinstance(result, list):
                for article in result:
                    clean = article['url'].split('?')[0]
                    if clean not in seen_urls:
                        seen_urls.add(clean)
                        article['url'] = clean
                        all_articles.append(article)
        logger.info(f"Fetched {len(all_articles)} articles")
        return all_articles
