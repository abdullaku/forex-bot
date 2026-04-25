import asyncio
import logging
import math
import re
from datetime import datetime, timedelta

import requests

from config import Config
from telegram_service import TelegramService
from facebook import FacebookService

logger = logging.getLogger(__name__)

DINAR_HOME_URL = "https://dinarapi.hediworks.site"

# ── ئەندازەی گۆڕانکاری بۆ پۆست کردن (دینار) ──────────────────
PRICE_CHANGE_THRESHOLD = 500  # هەر 500 دینار کۆی گۆڕانکاری


class DinarPoster:
    def __init__(self, telegram: TelegramService, facebook: FacebookService):
        self.telegram = telegram
        self.facebook = facebook
        self.config = Config()
        self._last_post_slot = None
        self._last_posted_value: float | None = None  # نرخی کاتی پۆستی دوایین
        self._accumulated_change: float = 0  # کۆی گۆڕانکاری هەڵگیراو

    def _headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        }

    def _fetch_dinar_price_sync(self) -> tuple[float | None, str | None]:
        try:
            response = requests.get(
                DINAR_HOME_URL,
                headers=self._headers(),
                timeout=10,
            )

            if response.status_code != 200:
                logger.error(f"Homepage body={response.text[:300]}")
                return None, None

            html = response.text

            m = re.search(
                r'"data"\s*:\s*\{\s*"value"\s*:\s*"?([\d,]+)"?\s*,\s*"created_at"\s*:\s*"([^"]+)"',
                html,
                re.S,
            )
            if m:
                value = float(m.group(1).replace(",", ""))
                created_at = m.group(2)
                return value, created_at

            m2 = re.search(r'100\s*دۆلار\s*.*?([\d,]{3,})', html, re.S)
            if m2:
                value = float(m2.group(1).replace(",", ""))
                return value, None

            logger.error("Could not find dollar price in homepage")
            return None, None

        except Exception as e:
            logger.error(f"❌ Homepage scrape error: {e}")
            return None, None

    async def _fetch_dinar_price(self) -> tuple[float | None, str | None]:
        return await asyncio.to_thread(self._fetch_dinar_price_sync)

    def _should_post(self, new_value: float) -> tuple[bool, str]:
        """
        دیاری دەکات ئایا دەبێت پۆست بکات یان نا.
        کۆی گۆڕانکاری هەڵدەگرێت — نەک لە نرخی دوایین پۆستکراو.
        نموونە: 300 + 200 = 500 → پۆست دەکات
        دەگەڕێتەوە (دەبێت_پۆست_بکات, ئاراستەی_گۆڕانکاری)
        ئاراستە: 'up' بەرزبوونەوە، 'down' دابەزین، '' یەکەم جار
        """
        if self._last_posted_value is None:
            # یەکەم جاره، بەبێ بەراوردکردن پۆست دەکات
            return True, ""

        diff = new_value - self._last_posted_value
        self._accumulated_change += diff

        logger.info(
            f"📊 کۆی گۆڕانکاری={self._accumulated_change:+,.0f} | "
            f"نرخی ئێستا={new_value:,.0f} | "
            f"نرخی دوایین={self._last_posted_value:,.0f}"
        )

        if abs(self._accumulated_change) >= PRICE_CHANGE_THRESHOLD:
            direction = "up" if self._accumulated_change > 0 else "down"
            self._accumulated_change = 0  # سفر دەکاتەوە بۆ دەوری داهاتوو
            return True, direction

        return False, ""

    def build_message(self, value: float, now: datetime, direction: str = "") -> str:
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%d/%m/%Y")
        channel = self.config.CHANNEL_USERNAME
        one_dollar = round(value / 100)

        # سەرپێچی گۆڕانکاری لەگەڵ ئیمۆجی
        if direction == "up":
            change_line = "⬆️ نرخ بەرز بوویەوە\n\n"
        elif direction == "down":
            change_line = "⬇️ نرخ دابەزی\n\n"
        else:
            change_line = ""

        return (
            "💵 نرخی دۆلاری نافەرمی\n"
            "لە بازاڕەکانی هەرێمی کوردستان\n\n"
            f"{change_line}"
            f"💲 100 دۆلار = {value:,.0f} دینار\n"
            f"💲 1 دۆلار  = {one_dollar:,.0f} دینار\n\n"
            f"🕐 {time_str} | {date_str}\n"
            f"🔔 {channel}"
        )

    def _is_working_hours(self, now: datetime) -> bool:
        return 8 <= now.hour < 24

    def _seconds_until_next_half_hour(self, now: datetime) -> int:
        if now.minute < 30:
            next_run = now.replace(minute=30, second=0, microsecond=0)
        else:
            next_run = (now + timedelta(hours=1)).replace(
                minute=0,
                second=0,
                microsecond=0,
            )

        return max(math.ceil((next_run - now).total_seconds()), 1)

    async def post_dinar(self) -> None:
        try:
            now = datetime.now(self.config.BAGHDAD_TZ)
            slot_key = now.strftime("%Y-%m-%d %H:%M")

            if self._last_post_slot == slot_key:
                logger.warning(f"⛔ Duplicate post prevented for slot {slot_key}")
                return

            value, created_at = await self._fetch_dinar_price()

            if not value:
                logger.warning("⚠️ DinarPoster: نرخ نەگەیشت")
                return

            # ── بەررسی ئایا کۆی گۆڕانکاری گەیشتە 500 ──────────────────────────
            should_post, direction = self._should_post(value)

            if not should_post:
                logger.info(
                    f"⏭️ کۆی گۆڕانکاری هێشتا نەگەیشتە {PRICE_CHANGE_THRESHOLD:,} | "
                    f"نرخی ئێستا={value:,.0f}"
                )
                return

            msg = self.build_message(value, now, direction)

            try:
                await self.telegram.send_message(msg)
            except Exception as e:
                logger.error(f"❌ DinarPoster Telegram error: {e}")

            try:
                await self.facebook.post(msg)
            except Exception as e:
                logger.error(f"❌ DinarPoster Facebook error: {e}")

            # نرخی نوێ بەخاترەوە بگرە
            old_value = self._last_posted_value
            self._last_posted_value = value
            self._last_post_slot = slot_key

            if old_value is not None:
                diff = value - old_value
                arrow = "⬆️" if diff > 0 else "⬇️"
                logger.info(
                    f"✅ DinarPoster پۆست کرا | 100$={value:,.0f} IQD | "
                    f"گۆڕانکاری={diff:+,.0f} {arrow} | created_at={created_at}"
                )
            else:
                logger.info(
                    f"✅ DinarPoster یەکەم پۆست | 100$={value:,.0f} IQD | created_at={created_at}"
                )

        except Exception as e:
            logger.error(f"❌ DinarPoster error: {e}")

    async def run(self) -> None:
        logger.info("💵 DinarPoster: دەستی پێکرد")

        while True:
            now = datetime.now(self.config.BAGHDAD_TZ)
            wait_seconds = self._seconds_until_next_half_hour(now)
            next_run_time = now + timedelta(seconds=wait_seconds)

            logger.info(
                f"⏳ Next run in {wait_seconds}s at {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await asyncio.sleep(wait_seconds)

            now = datetime.now(self.config.BAGHDAD_TZ)
            logger.info(f"⏱️ Tick: {now.strftime('%Y-%m-%d %H:%M:%S')}")

            if self._is_working_hours(now):
                await self.post_dinar()
            else:
                logger.info("🛌 لە کاتی کارکردن نییە")
