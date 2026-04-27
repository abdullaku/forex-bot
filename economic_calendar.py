import re
import logging
from datetime import datetime, timezone, timedelta

import aiohttp

logger = logging.getLogger(__name__)

RTL = "\u200f"  # Right-to-Left mark — دەستپێکی نووسین لای ڕاست


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
        # ── داتای نرخ و ئینفلاسیۆن ──
        "CPI":                              "نرخی بەرزی ژیان (CPI)",
        "Core CPI":                         "نرخی بەرزی ژیان بێ خۆراک و وزە",
        "PPI":                              "نرخی بەرهەمهێنان (PPI)",
        "Core PPI":                         "نرخی بەرهەمهێنان بێ خۆراک و وزە",
        "PCE Price Index":                  "پێوەری نرخی PCE",
        "Core PCE Price Index":             "پێوەری نرخی PCE بێ خۆراک و وزە",
        "Inflation Rate":                   "ڕێژەی ئینفلاسیۆن",
        "Inflation":                        "ئینفلاسیۆن",

        # ── کار و کارمەند ──
        "Non-Farm Payrolls":                "ژمارەی کارمەندی نوێ (NFP)",
        "Nonfarm Payrolls":                 "ژمارەی کارمەندی نوێ (NFP)",
        "NFP":                              "ژمارەی کارمەندی نوێ (NFP)",
        "Unemployment Rate":                "ڕێژەی بێکاری",
        "Unemployment":                     "بێکاری",
        "Average Hourly Earnings":          "تێکڕای مووچەی کاتژمێری",
        "Jobless Claims":                   "داواکاری بیمەی بێکاری",
        "Initial Jobless Claims":           "داواکاری بیمەی بێکاری (یەکەم جار)",
        "Continuing Jobless Claims":        "داواکاری بیمەی بێکاری (بەردەوام)",
        "ADP Nonfarm Employment":           "ژمارەی کارمەندی ADP",
        "Employment Change":                "گۆڕانکاری کارمەندی",
        "Labor Force Participation Rate":   "ڕێژەی بەشداری هێزی کار",

        # ── بەرهەمی ناوخۆ و گەشەی ئابووری ──
        "GDP":                              "بەرهەمی ناوخۆی گشتی (GDP)",
        "Gross Domestic Product":           "بەرهەمی ناوخۆی گشتی (GDP)",
        "GDP Growth Rate":                  "ڕێژەی گەشەی GDP",
        "Retail Sales":                     "فرۆشتنی لقی",
        "Core Retail Sales":                "فرۆشتنی لقی بێ ئۆتۆمبێل",
        "Industrial Production":            "بەرهەمهێنانی پیشەسازی",
        "Manufacturing PMI":                "پێوەری چالاکی پیشەسازی (PMI)",
        "Services PMI":                     "پێوەری چالاکی خزمەتگوزاری (PMI)",
        "Composite PMI":                    "پێوەری چالاکی گشتی (PMI)",
        "PMI":                              "پێوەری چالاکی (PMI)",
        "ISM Manufacturing PMI":            "پێوەری ISM بۆ پیشەسازی",
        "ISM Services PMI":                 "پێوەری ISM بۆ خزمەتگوزاری",
        "Trade Balance":                    "ترازووی بازرگانی",
        "Current Account":                  "هەژماری کارەبایی",
        "Consumer Confidence":              "باوەڕی بەکارهێنەر",
        "Consumer Sentiment":               "هەستی بەکارهێنەر",
        "Business Confidence":              "باوەڕی بازرگانی",
        "Durable Goods Orders":             "داواکاری کاڵای مانەوەدار",
        "Factory Orders":                   "داواکاری کارگە",
        "Housing Starts":                   "دەستپێکردنی بینا",
        "Building Permits":                 "مۆڵەتی بیناسازی",
        "Existing Home Sales":              "فرۆشتنی خانووی کۆن",
        "New Home Sales":                   "فرۆشتنی خانووی نوێ",

        # ── بانکی ناوەندی و نرخی فایدە ──
        "Interest Rate Decision":           "بڕیاری نرخی فایدە",
        "Interest Rate":                    "نرخی فایدە",
        "Fed Interest Rate Decision":       "بڕیاری نرخی فایدەی Fed",
        "ECB Interest Rate Decision":       "بڕیاری نرخی فایدەی ECB",
        "BoE Interest Rate Decision":       "بڕیاری نرخی فایدەی BoE",
        "BoJ Interest Rate Decision":       "بڕیاری نرخی فایدەی BoJ",
        "FOMC Statement":                   "بەیانامەی FOMC",
        "FOMC Meeting Minutes":             "تومارەکانی کۆبوونەوەی FOMC",
        "Fed Press Conference":             "کۆنفەرانسی رووداوی Fed",
        "Monetary Policy Statement":        "بەیانامەی سیاسەتی پارەیی",
        "Monetary Policy":                  "سیاسەتی پارەیی",
        "Quantitative Easing":              "ئاسانکاری بڕی پارە (QE)",
        "Balance Sheet":                    "ستاتی دارایی بانک",

        # ── وتارەکانی سەرۆکانی بانک ──
        "Fed Chair Powell Speaks":          "وتاری سەرۆکی Fed پاول",
        "Powell Speaks":                    "وتاری پاول (Fed)",
        "Lagarde Speaks":                   "وتاری لاگارد (ECB)",
        "Bailey Speaks":                    "وتاری بایلی (BoE)",
        "Ueda Speaks":                      "وتاری ئوێدا (BoJ)",

        # ── وشە و دوانەی گشتی ──
        "m/m":                              "(مانگانە)",
        "y/y":                              "(ساڵانە)",
        "q/q":                              "(چارەکانە)",
        "Flash":                            "پێشەوەختی",
        "Preliminary":                      "سەرەتایی",
        "Final":                            "کۆتایی",
        "Revised":                          "دەستکاریکراو",
        "Actual":                           "ڕاستەقینە",
        "Forecast":                         "پێشبینی",
        "Previous":                         "پێشتر",
    }

    def _now_baghdad(self):
        return datetime.now(self.BAGHDAD_TZ)

    def _translate_title(self, title: str) -> str:
        for en, ku in self.TITLE_TRANSLATE.items():
            title = re.sub(re.escape(en), ku, title, flags=re.IGNORECASE)
        return title

    def _extract_event_time(self, event_date: str) -> str:
        if "T" not in event_date:
            return ""
        event_dt = datetime.fromisoformat(event_date.replace("Z", "+00:00"))
        return event_dt.astimezone(self.BAGHDAD_TZ).strftime("%H:%M")

    @staticmethod
    def _strip_html(text: str) -> str:
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

                        line = f"{RTL}{flag} {event_time} › {title}"

                        if impact == "High":
                            high_events.append(line)
                        else:
                            medium_events.append(line)

        except Exception as e:
            logger.error(f"Calendar Error: {e}")

        if not high_events and not medium_events:
            return []

        lines = []
        lines.append(f"{RTL}🗓 {now.strftime('%d/%m/%Y')}")
        lines.append("━━━━━━━━━━━━━━━━━━━━━")

        if high_events:
            lines.append(f"{RTL}🔴 زۆر گرنگ")
            lines.extend(high_events)

        if medium_events:
            lines.append("")
            lines.append(f"{RTL}🟡 مامناوەند")
            lines.extend(medium_events)

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"{RTL}⚠️ کاتەکان بە کاتی هەولێر (UTC+3)")
        lines.append(f"{RTL}🔔 @KurdTraderKRD")

        return lines

    def build_telegram_msg(self, events: list) -> str:
        body = "\n".join(events)
        return f"{RTL}📅 <b>ڕۆژمێری ئابووری ئەمڕۆ</b>\n\n{body}"

    def build_facebook_msg(self, events: list) -> str:
        body = "\n".join(events)
        return f"{RTL}📅 ڕۆژمێری ئابووری ئەمڕۆ\n\n{body}"
