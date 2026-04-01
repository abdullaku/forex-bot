import asyncio
import logging
import math
import re
from datetime import datetime, timedelta

import requests

from config import Config
from telegram_service import TelegramService

logger = logging.getLogger(__name__)

DINAR_HOME_URL = "https://dinarapi.hediworks.site"


class DinarPoster:
    def __init__(self, telegram: TelegramService):
        self.telegram = telegram
        self.config = Config()
        self._last_post_slot = None
        self._last_value = None

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

    def build_message(self, value: float, now: datetime) -> str:
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%d/%m/%Y")
        channel = self.config.CHANNEL_USERNAME
        one_dollar = round(value / 100)

        return (
            "💵 نرخی دۆلاری نافەرمی\n"
            "لە بازاڕەکانی هەرێمی کوردستان\n\n"
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

            if self._last_value is not None and value == self._last_value:
                logger.info(
                    f"⏭️ DinarPoster: same value as previous post ({value:,.0f}), skip"
                )
                self._last_post_slot = slot_key
                return

            msg = self.build_message(value, now)
            await self.telegram.send_message(msg)

            self._last_value = value
            self._last_post_slot = slot_key

            logger.info(
                f"✅ DinarPoster: 100$ = {value:,.0f} IQD | source=homepage-scrape | created_at={created_at}"
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
