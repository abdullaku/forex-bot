import json
import logging
import os
from datetime import datetime, timezone, timedelta, time as dtime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import aiohttp

logger = logging.getLogger(__name__)


class CalendarService:
    """
    Economic calendar service for the channel.

    Design:
      - Trading Economics is the main provider when TRADING_ECONOMICS_API_KEY is set.
      - ForexFactory is kept only as fallback/cache, not as the main polling source.
      - The bot can tick every 30 seconds, but it checks local cached events most of the time.
      - External API is called only for daily refresh and short result windows around releases.
    """

    BAGHDAD_TZ = timezone(timedelta(hours=3))

    TE_BASE_URL = "https://api.tradingeconomics.com/calendar/country/{countries}/{start}/{end}"
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

    COUNTRY_FLAGS = {
        "United States": "🇺🇸",
        "Euro Area": "🇪🇺",
        "European Union": "🇪🇺",
        "Germany": "🇩🇪",
        "France": "🇫🇷",
        "Italy": "🇮🇹",
        "Spain": "🇪🇸",
        "United Kingdom": "🇬🇧",
        "Japan": "🇯🇵",
        "Canada": "🇨🇦",
        "Australia": "🇦🇺",
        "New Zealand": "🇳🇿",
        "Switzerland": "🇨🇭",
        "China": "🇨🇳",
        "Turkey": "🇹🇷",
    }

    COUNTRY_TO_CURRENCY = {
        "United States": "USD",
        "Euro Area": "EUR",
        "European Union": "EUR",
        "Germany": "EUR",
        "France": "EUR",
        "Italy": "EUR",
        "Spain": "EUR",
        "United Kingdom": "GBP",
        "Japan": "JPY",
        "Canada": "CAD",
        "Australia": "AUD",
        "New Zealand": "NZD",
        "Switzerland": "CHF",
        "China": "CNY",
    }

    def __init__(self, send_callback, fb_callback=None):
        self._send = send_callback
        self._fb = fb_callback

        self.provider = os.environ.get("CALENDAR_PROVIDER", "tradingeconomics").strip().lower()
        self.te_api_key = os.environ.get("TRADING_ECONOMICS_API_KEY", "").strip()
        self.te_countries = os.environ.get("TRADING_ECONOMICS_COUNTRIES", "All").strip() or "All"
        self.ff_fallback = os.environ.get("FOREX_FACTORY_FALLBACK", "true").strip().lower() != "false"

        self.daily_fetch_time = self._parse_clock(os.environ.get("DAILY_CALENDAR_FETCH_TIME", "08:55"))
        self.daily_post_time = self._parse_clock(os.environ.get("DAILY_CALENDAR_POST_TIME", "09:00"))
        self.pre_alert_minutes = int(os.environ.get("PRE_ALERT_MINUTES", "30"))
        self.result_poll_seconds = int(os.environ.get("RESULT_POLL_SECONDS", "60"))
        self.result_poll_window_minutes = int(os.environ.get("RESULT_POLL_WINDOW_MINUTES", "15"))
        self.normal_refresh_minutes = int(os.environ.get("CALENDAR_REFRESH_NORMAL_MINUTES", "360"))

        self.state_path = Path(os.environ.get("CALENDAR_STATE_FILE", ".calendar_state.json"))
        self._morning_posted: Optional[str] = None
        self._daily_fetched: Optional[str] = None
        self._alert_sent: set = set()
        self._result_sent: set = set()
        self._load_state()

        self._calendar_cache: list[dict] = []
        self._calendar_cache_at: Optional[datetime] = None
        self._last_result_fetch_at: Optional[datetime] = None

        self._ff_calendar_cache: list[dict] = []
        self._ff_calendar_cache_at: Optional[datetime] = None
        self._ff_backoff_until: Optional[datetime] = None
        self._ff_backoff_minutes: int = 0

    def _now(self) -> datetime:
        return datetime.now(self.BAGHDAD_TZ)

    def _parse_clock(self, value: str) -> dtime:
        try:
            hour, minute = value.strip().split(":", 1)
            return dtime(int(hour), int(minute), tzinfo=self.BAGHDAD_TZ)
        except Exception:
            logger.warning("Invalid time value %r, using 09:00", value)
            return dtime(9, 0, tzinfo=self.BAGHDAD_TZ)

    def _is_weekend(self, now: datetime) -> bool:
        return now.weekday() in (5, 6)

    def _state_today(self, now: datetime) -> str:
        return now.strftime("%Y-%m-%d")

    def _load_state(self) -> None:
        try:
            if not self.state_path.exists():
                return
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._morning_posted = data.get("morning_posted")
            self._daily_fetched = data.get("daily_fetched")
            self._alert_sent = set(data.get("alert_sent", []))
            self._result_sent = set(data.get("result_sent", []))
        except Exception as e:
            logger.warning("Calendar state could not be loaded: %s", e)

    def _save_state(self) -> None:
        try:
            data = {
                "morning_posted": self._morning_posted,
                "daily_fetched": self._daily_fetched,
                "alert_sent": sorted(self._alert_sent),
                "result_sent": sorted(self._result_sent),
            }
            self.state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Calendar state could not be saved: %s", e)

    def _reset_old_state_if_needed(self, now: datetime) -> None:
        today = self._state_today(now)
        if self._morning_posted and self._morning_posted != today:
            self._morning_posted = None
        if self._daily_fetched and self._daily_fetched != today:
            self._daily_fetched = None
        self._alert_sent = {x for x in self._alert_sent if x.startswith(today)}
        self._result_sent = {x for x in self._result_sent if x.startswith(today)}

    def _event_dt(self, event: dict) -> Optional[datetime]:
        date_str = event.get("date", "")
        if not date_str:
            return None
        try:
            if "T" in date_str and (date_str.endswith("Z") or "+" in date_str[10:]):
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(date_str)
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(self.BAGHDAD_TZ)
        except ValueError:
            return None

    def _event_id(self, event: dict) -> str:
        dt = self._event_dt(event)
        day = dt.strftime("%Y-%m-%d") if dt else self._now().strftime("%Y-%m-%d")
        raw = event.get("id") or f"{event.get('country', '')}|{event.get('title', '')}|{event.get('date', '')}"
        return f"{day}:{raw}"

    def _flag_for_event(self, event: dict) -> str:
        currency = event.get("currency", "")
        if currency in self.CURRENCY_FLAGS:
            return self.CURRENCY_FLAGS[currency]
        country = event.get("country", "")
        return self.COUNTRY_FLAGS.get(country, "🌍")

    def _filter_today(self, events: list[dict], now: Optional[datetime] = None) -> list[dict]:
        now = now or self._now()
        today = now.date()
        results = []
        for event in events:
            dt = self._event_dt(event)
            if not dt or dt.date() != today:
                continue
            if event.get("impact") not in ("High", "Medium"):
                continue
            results.append(event)
        return sorted(results, key=lambda e: self._event_dt(e) or now)

    def _empty(self, value) -> bool:
        if value is None:
            return True
        text = str(value).strip()
        return text == "" or text.lower() in {"none", "null", "nan", "-"}

    async def _broadcast(self, msg: str) -> None:
        await self._send(msg)
        if self._fb:
            try:
                await self._fb(msg)
            except Exception as e:
                logger.error("Calendar Facebook error: %s", e)

    def _normalize_te_event(self, item: dict) -> Optional[dict]:
        importance = item.get("Importance")
        try:
            importance = int(importance)
        except Exception:
            importance = 0

        if importance == 3:
            impact = "High"
        elif importance == 2:
            impact = "Medium"
        else:
            return None

        country = str(item.get("Country") or "").strip()
        currency_code = self.COUNTRY_TO_CURRENCY.get(country, "")
        title = str(item.get("Event") or item.get("Category") or "").strip()
        if not title:
            return None

        return {
            "provider": "Trading Economics",
            "id": str(item.get("CalendarId") or item.get("Ticker") or item.get("Symbol") or ""),
            "date": str(item.get("Date") or ""),
            "country": country,
            "currency": currency_code,
            "title": title,
            "category": str(item.get("Category") or "").strip(),
            "impact": impact,
            "actual": str(item.get("Actual") or "").strip(),
            "forecast": str(item.get("Forecast") or item.get("TEForecast") or "").strip(),
            "previous": str(item.get("Previous") or "").strip(),
            "revised": str(item.get("Revised") or "").strip(),
            "source": str(item.get("Source") or "Trading Economics").strip(),
            "url": str(item.get("URL") or "").strip(),
            "last_update": str(item.get("LastUpdate") or "").strip(),
        }

    def _te_url(self, now: datetime) -> str:
        start = (now.astimezone(timezone.utc).date() - timedelta(days=1)).isoformat()
        end = (now.astimezone(timezone.utc).date() + timedelta(days=1)).isoformat()
        countries = quote(self.te_countries, safe=",")
        return (
            self.TE_BASE_URL.format(countries=countries, start=start, end=end)
            + f"?c={quote(self.te_api_key, safe=':')}&importance=2,3&f=json"
        )

    async def _fetch_trading_economics(self, now: datetime) -> list[dict]:
        if not self.te_api_key:
            logger.warning("TRADING_ECONOMICS_API_KEY is missing; skipping Trading Economics")
            return []

        url = self._te_url(now)
        headers = {
            "User-Agent": "KurdTraderBot/1.0 (+https://t.me/KurdTraderKRD)",
            "Accept": "application/json,text/plain,*/*",
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("Trading Economics returned %s: %s", resp.status, body[:200])
                    return []
                data = await resp.json(content_type=None)

        if not isinstance(data, list):
            logger.warning("Trading Economics returned unexpected payload: %r", data)
            return []

        events = []
        for item in data:
            normalized = self._normalize_te_event(item)
            if normalized:
                events.append(normalized)
        return self._filter_today(events, now)

    def _normalize_ff_event(self, item: dict) -> Optional[dict]:
        impact = item.get("impact", "")
        if impact not in ("High", "Medium"):
            return None
        return {
            "provider": "ForexFactory",
            "id": str(item.get("id") or ""),
            "date": str(item.get("date") or ""),
            "country": "",
            "currency": str(item.get("currency") or ""),
            "title": str(item.get("title") or "").strip(),
            "category": "",
            "impact": impact,
            "actual": str(item.get("actual") or "").strip(),
            "forecast": str(item.get("forecast") or "").strip(),
            "previous": str(item.get("previous") or "").strip(),
            "revised": "",
            "source": "ForexFactory",
            "url": "",
            "last_update": "",
        }

    async def _fetch_forexfactory(self, now: datetime, force: bool = False) -> list[dict]:
        if not self.ff_fallback:
            return []

        if self._ff_calendar_cache_at and not force:
            age = (now - self._ff_calendar_cache_at).total_seconds()
            if age < 60 * 60:
                return self._filter_today(self._ff_calendar_cache, now)

        if self._ff_backoff_until is not None and now < self._ff_backoff_until:
            logger.info("ForexFactory backoff active; using cached fallback calendar")
            return self._filter_today(self._ff_calendar_cache, now)

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; KurdTraderBot/1.0; +https://t.me/KurdTraderKRD)",
            "Accept": "application/json,text/plain,*/*",
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(self.FF_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 429:
                        self._ff_backoff_minutes = min(max(self._ff_backoff_minutes * 2, 10), 60)
                        self._ff_backoff_until = now + timedelta(minutes=self._ff_backoff_minutes)
                        logger.warning(
                            "ForexFactory returned 429; fallback backing off for %s minutes",
                            self._ff_backoff_minutes,
                        )
                        return self._filter_today(self._ff_calendar_cache, now)
                    if resp.status != 200:
                        logger.warning("ForexFactory returned %s", resp.status)
                        return self._filter_today(self._ff_calendar_cache, now)
                    data = await resp.json(content_type=None)

            events = []
            for item in data:
                normalized = self._normalize_ff_event(item)
                if normalized:
                    events.append(normalized)

            self._ff_calendar_cache = events
            self._ff_calendar_cache_at = now
            self._ff_backoff_until = None
            self._ff_backoff_minutes = 0
            return self._filter_today(events, now)

        except Exception as e:
            logger.error("ForexFactory fallback fetch error: %s", e)
            return self._filter_today(self._ff_calendar_cache, now)

    async def _refresh_calendar(self, force: bool = False, reason: str = "normal") -> list[dict]:
        now = self._now()

        if self._calendar_cache_at and not force:
            age = (now - self._calendar_cache_at).total_seconds()
            if age < self.normal_refresh_minutes * 60:
                return self._filter_today(self._calendar_cache, now)

        events: list[dict] = []

        if self.provider in ("tradingeconomics", "te", "trading_economics"):
            try:
                events = await self._fetch_trading_economics(now)
            except Exception as e:
                logger.error("Trading Economics fetch error: %s", e)
                events = []

        if not events and self.ff_fallback:
            events = await self._fetch_forexfactory(now, force=force)

        if events:
            self._calendar_cache = events
            self._calendar_cache_at = now
            logger.info("Calendar refreshed from provider: events=%s reason=%s", len(events), reason)
        else:
            logger.warning("Calendar refresh returned no events; using existing cache if available")

        return self._filter_today(self._calendar_cache, now)

    async def _get_cached_today(self) -> list[dict]:
        return self._filter_today(self._calendar_cache, self._now())

    def _format_morning(self, events: list, now: datetime) -> str:
        high_lines = []
        medium_lines = []

        for event in events:
            dt = self._event_dt(event)
            time_str = dt.strftime("%H:%M") if dt else "??:??"
            flag = self._flag_for_event(event)
            title = event.get("title", "")
            country = event.get("country", "")
            country_part = f" ({country})" if country else ""
            line = f"{flag} {time_str} › {title}{country_part}"

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

        if not high_lines and not medium_lines:
            parts.append("\nNo high/medium impact events scheduled today.")

        parts.append("\n⏰ Times are Erbil time (UTC+3)")
        parts.append("📢 @KurdTraderKRD")

        return "\n".join(parts)

    def _format_alert(self, event: dict) -> str:
        dt = self._event_dt(event)
        time_str = dt.strftime("%H:%M") if dt else "??:??"
        flag = self._flag_for_event(event)
        title = event.get("title", "")
        forecast = event.get("forecast", "")
        previous = event.get("previous", "")
        country = event.get("country", "")

        lines = [
            f"⏰ Upcoming in {self.pre_alert_minutes} min",
            f"{flag} {time_str} › {title}",
        ]
        if country:
            lines.append(f"🌍 Country: {country}")
        if forecast:
            lines.append(f"📊 Forecast: {forecast}")
        if previous:
            lines.append(f"⏮ Previous: {previous}")
        lines.append("📢 @KurdTraderKRD")
        return "\n".join(lines)

    def _format_result(self, event: dict) -> str:
        actual = event.get("actual", "")
        if self._empty(actual):
            return ""

        dt = self._event_dt(event)
        time_str = dt.strftime("%H:%M") if dt else "??:??"
        flag = self._flag_for_event(event)
        title = event.get("title", "")
        forecast = event.get("forecast", "")
        previous = event.get("previous", "")
        revised = event.get("revised", "")
        country = event.get("country", "")

        lines = [
            "📊 Data Released",
            f"{flag} {time_str} › {title}",
        ]
        if country:
            lines.append(f"🌍 Country: {country}")
        lines.append(f"✅ Actual:   {actual}")
        if forecast:
            lines.append(f"📈 Forecast: {forecast}")
        if previous:
            lines.append(f"⏮ Previous: {previous}")
        if revised:
            lines.append(f"🔁 Revised: {revised}")
        lines.append("📢 @KurdTraderKRD")
        return "\n".join(lines)

    def _should_do_daily_fetch(self, now: datetime) -> bool:
        today = self._state_today(now)
        if self._daily_fetched == today:
            return False
        fetch_dt = datetime.combine(now.date(), self.daily_fetch_time, tzinfo=self.BAGHDAD_TZ)
        return now >= fetch_dt

    def _should_do_morning_post(self, now: datetime) -> bool:
        today = self._state_today(now)
        if self._morning_posted == today:
            return False
        post_dt = datetime.combine(now.date(), self.daily_post_time, tzinfo=self.BAGHDAD_TZ)
        return post_dt <= now <= post_dt + timedelta(minutes=10)

    def _event_is_in_result_window(self, event: dict, now: datetime) -> bool:
        dt = self._event_dt(event)
        if dt is None:
            return False
        minutes_past = (now - dt).total_seconds() / 60
        return 0 <= minutes_past <= self.result_poll_window_minutes

    def _result_poll_due(self, now: datetime) -> bool:
        if self._last_result_fetch_at is None:
            return True
        return (now - self._last_result_fetch_at).total_seconds() >= self.result_poll_seconds

    async def tick(self):
        now = self._now()
        self._reset_old_state_if_needed(now)

        if self._is_weekend(now):
            self._save_state()
            return

        today_key = self._state_today(now)

        if self._should_do_daily_fetch(now):
            await self._refresh_calendar(force=True, reason="daily_fetch")
            self._daily_fetched = today_key
            self._save_state()

        events = await self._get_cached_today()

        if not events and self._should_do_morning_post(now):
            events = await self._refresh_calendar(force=True, reason="morning_post_empty_cache")

        if self._should_do_morning_post(now):
            msg = self._format_morning(events, now)
            await self._broadcast(msg)
            self._morning_posted = today_key
            self._save_state()

        high_events = [e for e in events if e.get("impact") == "High"]

        needs_result_refresh = any(
            self._event_is_in_result_window(e, now) and self._event_id(e) not in self._result_sent
            for e in high_events
        )

        if needs_result_refresh and self._result_poll_due(now):
            self._last_result_fetch_at = now
            events = await self._refresh_calendar(force=True, reason="result_window")
            high_events = [e for e in events if e.get("impact") == "High"]

        for event in high_events:
            dt = self._event_dt(event)
            if dt is None:
                continue

            eid = self._event_id(event)
            minutes_until = (dt - now).total_seconds() / 60

            alert_window_start = self.pre_alert_minutes - 2
            alert_window_end = self.pre_alert_minutes + 2
            if alert_window_start <= minutes_until <= alert_window_end and eid not in self._alert_sent:
                msg = self._format_alert(event)
                await self._broadcast(msg)
                self._alert_sent.add(eid)
                self._save_state()

            if self._event_is_in_result_window(event, now) and eid not in self._result_sent:
                result_msg = self._format_result(event)
                if result_msg:
                    await self._broadcast(result_msg)
                    self._result_sent.add(eid)
                    self._save_state()

    async def fetch_calendar(self) -> list:
        now = self._now()
        if self._is_weekend(now):
            return []
        events = await self._refresh_calendar(force=True, reason="legacy_fetch_calendar")
        if not events:
            return []
        return self._format_morning(events, now).splitlines()

    def build_telegram_msg(self, events: list) -> str:
        return "\n".join(events)
