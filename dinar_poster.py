import asyncio
import logging
from datetime import datetime

import requests

from config import Config
from telegram_service import TelegramService

logger = logging.getLogger(__name__)

DINAR_API_URL = "https://dinarapi.hediworks.site/api/v2/nrxi-dolar"


class DinarPoster:
    def __init__(self, telegram: TelegramService):
        self.telegram = telegram
        self.config = Config()

    def _headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
            "Authorization": f"Bearer {self.config.DINAR_API_TOKEN}",
        }

    def _fetch_dinar_price_sync(self) -> tuple[float | None, str | None]:
        try:
            logger.info(f"🌐 Trying endpoint => {DINAR_API_URL}")

            response = requests.get(
                DINAR_API_URL,
                headers=self._headers(),
                timeout=10,
            )

            logger.info(
                f"📡 status={response.status_code} url={response.url}"
            )

            if response.status_code != 200:
                logger.error(f"API body={response.text}")
                return None, None

            data = response.json()
            logger.info(f"📦 API json={data}")

            inner = data.get("data", {})
            return inner.get("value"), inner.get("created_at")

        except Exception as e:
            logger.error(f"❌ API error: {e}")
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
        # return 8 <= now.hour < 24  # بۆ production

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
                f"✅ DinarPoster: 100$ = {value:,.0f} IQD | created_at={created_at}"
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
