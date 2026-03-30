import asyncio
import logging
from datetime import datetime

import aiohttp

from config import Config
from telegram_service import TelegramService

logger = logging.getLogger(__name__)

DINAR_API_URL = "https://dinarapi.hediworks.site/api/v2/get-price?id=5&location=erbil"


class DinarPoster:
    """
    هەر کاتژمێرێک نرخی نا فەرمی 100 دۆلار بە دینار لە بازاڕی هەولێر دەنێرێت.
    کاتژمێر 8 بەیانی تا 12 شەو (UTC+3).
    """

    def __init__(self, telegram: TelegramService):
        self.telegram = telegram
        self.config = Config()

    async def _fetch_dinar_price(self) -> tuple[float | None, str | None]:
        token = self.config.DINAR_API_TOKEN
        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    DINAR_API_URL,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"DinarAPI status {resp.status} body={text}")
                        return None, None
                    data = await resp.json()
                    return data.get("value"), data.get("created_at")
        except Exception as e:
            logger.error(f"DinarAPI fetch error: {e}")
            return None, None

    def build_message(self, value: float, now: datetime) -> str:
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%d/%m/%Y")
        channel = self.config.CHANNEL_USERNAME
        one_dollar = value / 100

        return (
            "💵 نرخی نا فەرمی دینار — هەولێر\n\n"
            f"🏙️ شار: هەولێر\n"
            f"💲 100 دۆلار = {value:,.0f} دینار\n"
            f"💲 1 دۆلار  = {one_dollar:,.0f} دینار\n\n"
            f"🕐 {time_str} | {date_str}\n"
            f"🔔 {channel}"
        )

    def _is_working_hours(self, now: datetime) -> bool:
        """کاتژمێر 8 بەیانی تا 12 شەو"""
        return 8 <= now.hour < 24

    async def post_dinar(self) -> None:
        try:
            value, _ = await self._fetch_dinar_price()
            if not value:
                logger.warning("⚠️ DinarPoster: نرخ نەگەیشت")
                return
            now = datetime.now(self.config.BAGHDAD_TZ)
            msg = self.build_message(value, now)
            await self.telegram.send_message(msg)
            logger.info(f"✅ DinarPoster: 100$ = {value:,.0f} IQD")
        except Exception as e:
            logger.error(f"❌ DinarPoster error: {e}")

    async def run(self) -> None:
        """هەر کاتژمێرێک نرخ دەنێرێت — چاوەڕوانی تا :00 دقیقە"""
        logger.info("💵 DinarPoster: دەستی پێکرد")
        while True:
            now = datetime.now(self.config.BAGHDAD_TZ)
            wait_seconds = (60 - now.minute) * 60 - now.second
            wait_seconds = max(wait_seconds, 1)
            await asyncio.sleep(wait_seconds)

            now = datetime.now(self.config.BAGHDAD_TZ)
            if self._is_working_hours(now):
                await self.post_dinar()
