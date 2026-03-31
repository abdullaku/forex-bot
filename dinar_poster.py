import asyncio
import logging
import re
from datetime import datetime

import requests

from config import Config
from telegram_service import TelegramService

logger = logging.getLogger(__name__)

DINAR_HOME_URL = "https://dinarapi.hediworks.site"


class DinarPoster:
    def __init__(self, telegram: TelegramService):
        self.telegram = telegram
        self.config = Config()

    def _headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        }

    def _fetch_dinar_price_sync(self) -> tuple[float | None, str | None]:
        try:
            logger.info(f"🌐 Trying homepage => {DINAR_HOME_URL}")

            response = requests.get(
                DINAR_HOME_URL,
                headers=self._headers(),
                timeout=10,
            )

            logger.info(f"📡 status={response.status_code} url={response.url}")

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

    def build_message(self, value: float, now: datetime, created_at: str | None) -> str:
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%d/%m/%Y")
        channel = self.config.CHANNEL_USERNAME
        one_dollar = value / 100
        freshness = f"\n🗂️ API Time: {created_at}" if created_at else ""

        return (
            "💵 نرخی دۆلار بە دینار\n\n"
            f"💲 100 دۆلار = {value:,.0f} دینار\n"
            f"💲 1 دۆلار  = {one_dollar:,.0f} دینار"
            f"{freshness}\n\n"
            f"🕐 {time_str} | {date_str}\n"
            f"🔔 {channel}"
        )

    def _is_working_hours(self, now: datetime) -> bool:
        return True  # بۆ debug
        # return 8 <= now.hour < 24

    async def post_dinar(self) -> None:
        try:
            value, created_at = await self._fetch_dinar_price()

            if not value:
                logger.warning("⚠️ DinarPoster: نرخ نەگەیشت")
                return

            now = datetime.now(self.config.BAGHDAD_TZ)
            msg = self.build_message(value, now, created_at)
            await self.telegram.send_message(msg)

            logger.info(
                f"✅ DinarPoster: 100$ = {value:,.0f} IQD | source=homepage-scrape | created_at={created_at}"
            )

        except Exception as e:
            logger.error(f"❌ DinarPoster error: {e}")

    async def run(self) -> None:
        logger.info("💵 DinarPoster: دەستی پێکرد")

        while True:
            now = datetime.now(self.config.BAGHDAD_TZ)
            logger.info(f"⏱️ DinarPoster tick: {now.strftime('%Y-%m-%d %H:%M:%S')}")

            if self._is_working_hours(now):
                await self.post_dinar()

            await asyncio.sleep(60)
