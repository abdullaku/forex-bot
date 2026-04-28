import re
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class CalendarService:
    BAGHDAD_TZ = timezone(timedelta(hours=3))
    FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

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

    def __init__(self, send_callback, fb_callback=None):
        """
        send_callback: async function(message: str) -> None
            Called by this service to send messages to Telegram.
        fb_callback: async function(message: str) -> None (optional)
            Called by this service to send messages to Facebook.
        """
        self._send = send_callback
        self._fb = fb_callback
        self._morning_posted: Optional[str] = None   # date string YYYY-MM-DD
        self._alert_sent: set = set()                # event_ids already alerted
        self._result_sent: set = set()               # event_ids already result-posted

    # ── helpers ──────────────────────────────────────────────────────────────

    def _now(self) -> datetime:
        return datetime.now(self.BAGHDAD_TZ)

    def _is_weekend(self, now: datetime) -> bool:
        # weekday(): 0=Mon … 4=Fri, 5=Sat, 6=Sun
        return now.weekday() in (5, 6)

    def _event_dt(self, event: dict) -> Optional[datetime]:
        date_str = event.get("date", "")
        if "T" not in date_str:
            return None
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.astimezone(self.BAGHDAD_TZ)
        except ValueError:
            return None

    def _event_id(self, event: dict) -> str:
        return event.get("id", "") or event.get("title", "") + event.get("date", "")

    async def _broadcast(self, msg: str) -> None:
        """Send to Telegram (required) and Facebook (optional)."""
        await self._send(msg)
        if self._fb:
            try:
                await self._fb(msg)
            except Exception as e:
                logger.error(f"Calendar Facebook error: {e}")

    # ── fetch ─────────────────────────────────────────────────────────────────

    async def _fetch_today(self) -> list:
        """Return today's High/Medium events from ForexFactory."""
        now = self._now()
        today = now.strftime("%Y-%m-%d")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.FF_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning(f"ForexFactory returned {resp.status}")
                        return []
                    data = await resp.json(content_type=None)

            results = []
            for event in data:
                event_date = event.get("date", "")
                if today not in event_date:
                    continue
                if event.get("impact", "") not in ("High", "Medium"):
                    continue
                results.append(event)
            return results

        except Exception as e:
            logger.error(f"CalendarService fetch error: {e}")
            return []

    # ── format ───────────────────────────────────────────────────────────────

    def _format_morning(self, events: list, now: datetime) -> str:
        """Build the 09:00 morning calendar post — English, left-aligned."""
        high_lines = []
        medium_lines = []

        for event in events:
            dt = self._event_dt(event)
            time_str = dt.strftime("%H:%M") if dt else "??:??"
            flag = self.CURRENCY_FLAGS.get(event.get("currency", ""), "🌍")
            title = event.get("title", "")
            line = f"{flag} {time_str} › {title}"

            if event.get("impact") == "High":
                high_lines.append(line)
            else:
                medium_lines.append(line)

        date_str = now.strftime("%d/%m/%Y")
        parts = [f"📅 Economic Calendar — Today\n🗓 {date_str}"]

        if high_lines:
            parts.append("\n🔴 High Impact")
            parts.extend(high_lines)

        if medium_lines:
            parts.append("\n🟡 Medium Impact")
            parts.extend(medium_lines)

        parts.append("\n⏰ Times are Erbil time (UTC+3)")
        parts.append("📢 @KurdTraderKRD")

        return "\n".join(parts)

    def _format_alert(self, event: dict) -> str:
        """30-minute warning before a High event."""
        dt = self._event_dt(event)
        time_str = dt.strftime("%H:%M") if dt else "??:??"
        flag = self.CURRENCY_FLAGS.get(event.get("currency", ""), "🌍")
        title = event.get("title", "")
        forecast = event.get("forecast", "")
        previous = event.get("previous", "")

        lines = [
            f"⏰ Upcoming in 30 min",
            f"{flag} {time_str} › {title}",
        ]
        if forecast:
            lines.append(f"📊 Forecast: {forecast}")
        if previous:
            lines.append(f"⏮ Previous: {previous}")
        lines.append("📢 @KurdTraderKRD")
        return "\n".join(lines)

    def _format_result(self, event: dict) -> str:
        """Actual result post after event time."""
        dt = self._event_dt(event)
        time_str = dt.strftime("%H:%M") if dt else "??:??"
        flag = self.CURRENCY_FLAGS.get(event.get("currency", ""), "🌍")
        title = event.get("title", "")
        actual = event.get("actual", "")
        forecast = event.get("forecast", "")
        previous = event.get("previous", "")

        if not actual:
            return ""

        lines = [
            f"📊 Data Released",
            f"{flag} {time_str} › {title}",
            f"✅ Actual:   {actual}",
        ]
        if forecast:
            lines.append(f"📈 Forecast: {forecast}")
        if previous:
            lines.append(f"⏮ Previous: {previous}")
        lines.append("📢 @KurdTraderKRD")
        return "\n".join(lines)

    # ── main loop tick ────────────────────────────────────────────────────────

    async def tick(self):
        """
        Call this every 30 seconds from your main loop.
        Handles:
          1. 09:00 morning post (Mon–Fri only)
          2. 30-min pre-alert for High events
          3. Result post after event time (polls until actual appears)
        """
        now = self._now()

        if self._is_weekend(now):
            return

        events = await self._fetch_today()

        # ── ١. پۆستی بەیانی ٩:٠٠ ──
        today_key = now.strftime("%Y-%m-%d")
        if now.hour == 9 and now.minute < 5 and self._morning_posted != today_key:
            if events:
                msg = self._format_morning(events, now)
                await self._broadcast(msg)
            self._morning_posted = today_key

        # ── ٢ و ٣. هەواڵی High تەنها ──
        high_events = [e for e in events if e.get("impact") == "High"]

        for event in high_events:
            dt = self._event_dt(event)
            if dt is None:
                continue

            eid = self._event_id(event)
            minutes_until = (dt - now).total_seconds() / 60

            # ── ٢. ئاگادارکردنەوەی ٣٠ خولەک پێش ──
            if 28 <= minutes_until <= 32 and eid not in self._alert_sent:
                msg = self._format_alert(event)
                await self._broadcast(msg)
                self._alert_sent.add(eid)

            # ── ٣. ئەنجامەکە دوای دەرچوون (تا نیو کاتژمێر) ──
            minutes_past = -minutes_until
            if 0 <= minutes_past <= 35 and eid not in self._result_sent:
                result_msg = self._format_result(event)
                if result_msg:
                    await self._broadcast(result_msg)
                    self._result_sent.add(eid)

    # ── helpers for app.py ───────────────────────────────────────────────────

    async def fetch_calendar(self) -> list:
        """Legacy method — returns formatted lines for the morning post."""
        now = self._now()
        if self._is_weekend(now):
            return []
        events = await self._fetch_today()
        if not events:
            return []
        return self._format_morning(events, now).splitlines()

    def build_telegram_msg(self, events: list) -> str:
        return "\n".join(events)

    def build_facebook_msg(self, events: list) -> str:
        return "\n".join(events)
