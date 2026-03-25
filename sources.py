import asyncio
import aiohttp
import logging
from datetime import datetime, timezone, timedelta
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
        "Iraq Business News": {"url": "https://www.iraq-businessnews.com/feed", "category": "iraq_economy"},
    }

    FOREX_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "GOLD", "WTI", "OIL", "USD"]
    # لیستەکەمان هێشتووەتەوە بەڵام لە خوارەوە بەکاری ناهێنین بۆ سانسۆر
    FOREX_KEYWORDS = ["forex", "currency", "dollar", "euro", "pound", "yen", "gold", "oil", "inflation", "fed", "cpi", "market"]

    async def fetch_calendar(self):
        BAGHDAD_TZ = timezone(timedelta(hours=3))
        now = datetime.now(BAGHDAD_TZ)
        if now.weekday() in [5, 6]: return []

        high_events = []
        medium_events = []
        try:
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        today = now.strftime('%Y-%m-%d')
                        CURRENCY_FLAGS = {"USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵", "CAD": "🇨🇦", "AUD": "🇦🇺", "NZD": "🇳🇿", "CHF": "🇨🇭", "CNY": "🇨🇳"}
                        TITLE_TRANSLATE = {"m/m": "مانگانە", "y/y": "ساڵانە", "q/q": "چارەکانە", "CPI": "نرخی بەرزی ژیان", "GDP": "بەرهەمی ناوخۆ", "NFP": "کارمەندی نوێ", "Retail Sales": "فرۆشتنی لق", "Interest Rate": "ڕێژەی سوود", "Unemployment": "بێکاری", "PPI": "نرخی بەرهەمهێنان", "PMI": "پێوەری چالاکی"}

                        for event in data:
                            if today not in event.get('date', ''): continue
                            impact = event.get('impact', '')
                            if impact not in ['High', 'Medium']: continue
                            currency = event.get('currency', '')
                            flag = CURRENCY_FLAGS.get(currency, '🌐')
                            title = event.get('title', '')
                            for en, ku in TITLE_TRANSLATE.items(): title = title.replace(en, ku)
                            
                            time = ''
                            if 'T' in event.get('date', ''):
                                event_dt = datetime.fromisoformat(event.get('date', '').replace('Z', '+00:00'))
                                time = event_dt.astimezone(BAGHDAD_TZ).strftime('%H:%M')

                            line = f"{flag} {time} › {title}"
                            if impact == 'High': high_events.append(("🔴", line))
                            else: medium_events.append(("🟡", line))
        except Exception as e: logger.error(f"Calendar Error: {e}")
        
        if not high_events and not medium_events: return []
        result = [f"ڕۆژمێری ئابووری\n🗓 ئەمڕۆ | {now.strftime('%d/%m/%Y')}\n"]
        if high_events:
            result.append("🔴 گرنگ")
            for _, l in high_events: result.append(l)
        if medium_events:
            result.append("\n🟡 مامناوەند")
            for _, l in medium_events: result.append(l)
        result.append("\n🔔 @KurdTraderKRD")
        return result

    def detect_pairs(self, text):
        return [p for p in self.FOREX_PAIRS if p.upper() in text.upper()]

    async def fetch_rss(self, source_name, feed_info):
        articles = []
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(feed_info["url"], timeout=15) as resp:
                    if resp.status == 200:
                        soup = BeautifulSoup(await resp.text(), 'xml')
                        for item in soup.find_all('item')[:10]: # زیادکردنی ژمارەی هەواڵەکان بۆ ١٠
                            title = item.find('title').text.strip() if item.find('title') else ""
                            summary = item.find('description').text.strip() if item.find('description') else ""
                            url = item.find('link').text.strip() if item.find('link') else ""
                            
                            # لێرەدا سانسۆری وشەمان لابرد بۆ ئەوەی AI بڕیار بدات
                            articles.append({
                                "title": title, "summary": summary[:500],
                                "url": url, "source": source_name,
                                "category": feed_info["category"],
                                "pairs": self.detect_pairs(title + " " + summary),
                                "published_at": datetime.now().isoformat()
                            })
        except Exception as e: logger.error(f"Error {source_name}: {e}")
        return articles

    async def fetch_all(self):
        tasks = [self.fetch_rss(name, info) for name, info in self.RSS_FEEDS.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_articles = []
        seen_urls = set()
        for result in results:
            if isinstance(result, list):
                for article in result:
                    clean_url = article['url'].split('?')[0]
                    if clean_url not in seen_urls:
                        seen_urls.add(clean_url)
                        all_articles.append(article)
        return all_articles
