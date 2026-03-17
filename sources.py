import asyncio
import aiohttp
import logging
from datetime import datetime
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class NewsScraper:
    RSS_FEEDS = {
        "CNBC": {"url": "https://www.cnbc.com/id/10000664/device/rss/rss.html", "category": "economic_news"},
        "Bloomberg": {"url": "https://feeds.bloomberg.com/markets/news.rss", "category": "economic_news"},
        "Fox Business": {"url": "https://moxie.foxbusiness.com/google-publisher/markets.xml", "category": "economic_news"},
    }

    FOREX_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "GOLD", "WTI", "OIL", "USD"]
    FOREX_KEYWORDS = ["forex", "currency", "dollar", "euro", "pound", "yen", "gold", "oil", "inflation", "fed", "cpi", "market"]

    # --- ١. ئەجێندای ئابووری (Economic Calendar) ---
    async def fetch_calendar(self):
        events = []
        try:
            url = "https://www.investing.com/economic-calendar/"
            headers = {"User-Agent": "Mozilla/5.0"}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        soup = BeautifulSoup(await resp.text(), 'html.parser')
                        table = soup.find('table', id='economicCalendarData')
                        rows = table.find_all('tr', class_='js-event-item')
                        for row in rows[:10]:
                            impact_icons = row.find('td', class_='sentiment').find_all('i', class_='grayFullBullishIcon')
                            impact_level = len(impact_icons)
                            
                            if impact_level >= 2: # تەنها هەواڵە گرنگەکان
                                time = row.find('td', class_='time').text.strip()
                                currency = row.find('td', class_='left flagCur').text.strip()
                                event = row.find('td', class_='event').text.strip()
                                
                                emoji = "🔥" if impact_level == 3 else "⚠️"
                                events.append(f"{emoji} {time} | {currency} | {event}")
        except Exception as e:
            logger.error(f"Error fetching calendar: {e}")
        return events

    # --- ٢. هەستی بازاڕ (Market Sentiment) ---
    async def fetch_sentiment(self):
        sentiment_data = []
        try:
            # نموونەی داتای باو بۆ جووتە دراوەکان (دەکرێت لە API یان ماڵپەڕی وەک Myfxbook وەربگیرێت)
            pairs = ["EUR/USD", "GBP/USD", "XAU/USD", "USD/JPY"]
            # لێرەدا دەتوانیت بە شێوەی Static یان Scraper دایبنێیت
            for pair in pairs:
                # ئەمە وەک نموونە داتایەکی گشتییە، دەکرێت بەپێی کات بیگۆڕیت
                sentiment_data.append(f"📊 {pair}: 🔵 کڕین 52% | 🔴 فرۆشتن 48%")
        except Exception as e:
            logger.error(f"Error fetching sentiment: {e}")
        return sentiment_data

    # --- ٣. کورتەی بازاڕ (Market Wrap) ---
    async def fetch_market_wrap(self):
        summary = "📝 **کورتەی کۆتایی ڕۆژ:**\n"
        try:
            # لێرەدا دەتوانین نرخەکان بەراورد بکەین (ئەمە پێویستی بە نرخەکانە)
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
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(feed_info["url"], timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        root = ET.fromstring(text)
                        ns = {'atom': 'http://www.w3.org/2005/Atom', 'media': 'http://search.yahoo.com/mrss/'}
                        items = root.findall('.//item') or root.findall('.//atom:entry', ns)
                        
                        for item in items[:5]:
                            title = (item.findtext('title') or item.findtext('atom:title', namespaces=ns) or "").strip()
                            summary = (item.findtext('description') or item.findtext('atom:summary', namespaces=ns) or "").strip()
                            url = (item.findtext('link') or item.findtext('atom:link', namespaces=ns) or "").strip()
                            
                            image_url = None
                            # هەوڵدان بۆ دۆزینەوەی وێنە بە چەند ڕێگەیەک
                            media = item.find('{http://search.yahoo.com/mrss/}content') or \
                                    item.find('{http://search.yahoo.com/mrss/}thumbnail') or \
                                    item.find('.//media:content', namespaces=ns)
                            
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
                    clean = article['url'].split('?')[0]
                    if clean not in seen_urls:
                        seen_urls.add(clean)
                        article['url'] = clean
                        all_articles.append(article)
        return all_articles
