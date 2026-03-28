import re
import logging
from datetime import datetime, timezone, timedelta

import aiohttp

logger = logging.getLogger(__name__)


class CalendarService:
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

    @staticmethod
    def _strip_html(text: str) -> str:
        # ✅ هەموو HTML تاگەکان دەزالێتەوە بۆ Facebook
        return re.sub(r"<[^>]+>", "", text).strip()

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

    def build_telegram_msg(self, events: list) -> str:
        # ✅ تەنها Telegram تاگی HTML بەکاردێنێت
        body = "\n".join(events)
        return f"📅 <b>ڕۆژژمێری ئابووری ئەمڕۆ</b>\n\n{body}"

    def build_facebook_msg(self, events: list) -> str:
        # ✅ Facebook — بێ HTML تاگ
        body = "\n".join(events)
        return f"📅 ڕۆژژمێری ئابووری ئەمڕۆ\n\n{body}"
