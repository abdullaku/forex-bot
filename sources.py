import asyncio
import aiohttp
import logging
from datetime import datetime, timezone, timedelta
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
    BAGHDAD_TZ = timezone(timedelta(hours=3))

    CURRENCY_FLAGS = {
        "USD": "🇺🇸",
        "EUR": "🇪🇺",
        "GBP": "🇬🇧",
        "JPY": "🇯🇵",
        "CAD": "🇨🇦",
        "AUD": "🇦🇺",
        "NZD": "🇳🇿",
        "CHF": "🇨🇭",
        "CNY": "🇨🇳",
    }

    TITLE_TRANSLATE = {
        "m/m": "مانگانە",
        "y/y": "ساڵانە",
        "q/q": "چارەکانە",
        "CPI": "نرخی بەرزی ژیان",
        "GDP": "بەرهەمی ناوخۆ",
        "NFP": "کارمەندی نوێ",
        "Retail Sales": "فرۆشتنی لق",
        "Interest Rate": "ڕێژەی سوود",
        "Unemployment": "بێکاری",
        "PPI": "نرخی بەرهەمهێنان",
        "PMI": "پێوەری چالاکی",
    }

    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def _now_baghdad(self):
        return datetime.now(self.BAGHDAD_TZ)

    def _translate_title(self, title: str) -> str:
        for en, ku in self.TITLE_TRANSLATE.items():
            title = title.replace(en, ku)
        return title

    def _extract_event_time(self, event_date: str) -> str:
        if "T" not in event_date:
            return ""

        event_dt = datetime.fromisoformat(event_date.replace("Z", "+00:00"))
        return event_dt.astimezone(self.BAGHDAD_TZ).strftime("%H:%M")

    def detect_pairs(self, text):
        return [pair for pair in self.FOREX_PAIRS if pair.upper() in text.upper()]

    async def fetch_calendar(self):
        now = self._now_baghdad()

        if now.weekday() in [5, 6]:
            return []

        high_events = []
        medium_events = []

        try:
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return []

                    data = await resp.json()
                    today = now.strftime("%Y-%m-%d")

                    for event in data:
                        event_date = event.get("date", "")
                        if today not in event_date:
                            continue

                        impact = event.get("impact", "")
                        if impact not in ["High", "Medium"]:
                            continue

                        currency = event.get("currency", "")
                        flag = self.CURRENCY_FLAGS.get(currency, "🌐")

                        title = self._translate_title(event.get("title", ""))
                        event_time = self._extract_event_time(event_date)

                        line = f"{flag} {event_time} › {title}"

                        if impact == "High":
                            high_events.append(("🔴", line))
                        else:
                            medium_events.append(("🟡", line))

        except Exception as e:
            logger.error(f"Calendar Error: {e}")

        if not high_events and not medium_events:
            return []

        result = [f"ڕۆژمێری ئابووری\n🗓 ئەمڕۆ | {now.strftime('%d/%m/%Y')}\n"]

        if high_events:
            result.append("🔴 گرنگ")
            for _, line in high_events:
                result.append(line)

        if medium_events:
            result.append("\n🟡 مامناوەند")
            for _, line in medium_events:
                result.append(line)

        result.append("\n🔔 @KurdTraderKRD")
        return result

    def _parse_rss_item(self, item, source_name, category):
        title = item.find("title").text.strip() if item.find("title") else ""
        summary = item.find("description").text.strip() if item.find("description") else ""
        url = item.find("link").text.strip() if item.find("link") else ""

        return {
            "title": title,
            "summary": summary[:500],
            "url": url,
            "source": source_name,
            "category": category,
            "pairs": self.detect_pairs(title + " " + summary),
            "published_at": datetime.now().isoformat(),
        }

    async def fetch_rss(self, source_name, feed_info):
        articles = []

        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(feed_info["url"], timeout=15) as resp:
                    if resp.status != 200:
                        return articles

                    soup = BeautifulSoup(await resp.text(), "xml")

                    for item in soup.find_all("item")[:10]:
                        article = self._parse_rss_item(
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
