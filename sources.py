import asyncio
import aiohttp
import logging
from datetime import datetime
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class NewsScraper:
    RSS_FEEDS = {
        "CNBC": {"url": "https://www.cnbc.com/id/10000311/device/rss/rss.html", "category": "global_markets"},
        "Bloomberg": {"url": "https://www.bloomberg.com/feeds/bview/rss.xml", "category": "analysis"},
        "Fox Business": {"url": "https://moxie.foxbusiness.com/google-publisher/markets.xml", "category": "us_markets"},
        "CNBC Europe": {"url": "https://www.cnbc.com/id/19793763/device/rss/rss.html", "category": "europe_forex"},
        "CNBC Asia": {"url": "https://www.cnbc.com/id/19832390/device/rss/rss.html", "category": "asia_forex"},
        "Bloomberg Quicktake": {"url": "https://feeds.bloomberg.com/markets/news.rss", "category": "economic_news"},
    }

    FOREX_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "GOLD", "WTI", "OIL", "USD"]
    FOREX_KEYWORDS = ["forex", "currency", "dollar", "euro", "pound", "yen", "gold", "oil", "inflation", "fed", "cpi", "market"]

    async def fetch_calendar(self):
        events = []
        try:
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        today = datetime.now().strftime('%Y-%m-%d')
                        for event in data:
                            if today not in event.get('date', ''):
                                continue
                            impact = event.get('impact', '')
                            if impact not in ['High', 'Medium']:
                                continue
                            currency = event.get('currency', '')
                            title = event.get('title', '')
                            time = event.get('date', '').split('T')[1][:5] if 'T' in event.get('date', '') else ''
                            emoji = "🔥" if impact == 'High' else "⚠️"
                            events.append(f"{emoji} {time} | {currency} | {title}")
        except Exception as e:
            logger.error(f"Error fetching calendar: {e}")
        return events

    async def fetch_sentiment(self):
        sentiment_data = []
        try:
            pairs = ["EUR/USD", "GBP/USD", "XAU/USD", "USD/JPY"]
            for pair in pairs:
                sentiment_data.append(f"📊 {pair}: 🔵 کڕین 52% | 🔴 فرۆشتن 48%")
        except Exception as e:
            logger.error(f"Error fetching sentiment: {e}")
        return sentiment_data

    async def fetch_market_wrap(self):
        summary = "📝 **کورتەی کۆتایی ڕۆژ:**\n"
        try:
            summary += "• بازاڕی ئەمریکا بە جێگیری کۆتایی هات.\n"
            summary += "• زێڕ لە ژێر فشاری داتاکانی هەڵاوساندایە.\n"
            summary += "• دۆلار بەرامبەر دراوەکان بەهێزبوونی بەخۆوە بینی."
        except:
            summary = "کورتەی بازاڕ ئێستا بەردەست نییە."
        return summary

    def detect_pairs(self, text):
        return [p for p in self.FOREX_PAIRS if p.upper() in text.upper()]

    def is_forex_relevant(self, title, summary):
        text = (title + " " + summary).lower()
        return any(k.lower() in text for k in self.FOREX_KEYWORDS)

    async def fetch_rss(self, source_name, feed_info):
        articles = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(feed_info["url"], timeout=15) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        soup = BeautifulSoup(text, 'xml')
                        items = soup.find_all('item')
                        for item in items[:5]:
                            title = (item.find('title').text if item.find('title') else "").strip()
                            summary = (item.find('description').text if item.find('description') else "").strip()
                            url = (item.find('link').text if item.find('link') else "").strip()
                            image_url = None
                            media = item.find('media:content') or item.find('enclosure') or item.find('media:thumbnail')
                            if media is not None:
                                image_url = media.get('url')
                            if not self.is_forex_relevant(title, summary):
                                continue
                            articles.append({
                                "title": title, "summary": summary[:500],
                                "url": url, "source": source_name,
                                "category": feed_info["category"],
                                "pairs": self.detect_pairs(title + " " + summary),
                                "image_url": image_url,
                                "published_at": datetime.now().isoformat(),
                                "title_ku": "", "summary_ku": ""
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
                    clean = article['url'].split('?')[0].split('#')[0]
                    if clean not in seen_urls:
                        seen_urls.add(clean)
                        article['url'] = clean
                        all_articles.append(article)
        return all_articles
