import asyncio
import logging
from datetime import datetime

import requests

from config import Config
from telegram_service import TelegramService

logger = logging.getLogger(__name__)

DINAR_API_URLS = [
    {
        "name": "get-price-erbil",
        "url": "https://dinarapi.hediworks.site/api/v2/get-price?id=5&location=erbil",
        "format": "flat",
        "auth": True,
    },
    {
        "name": "nrxi-dolar",
        "url": "https://dinarapi.hediworks.site/api/v2/nrxi-dolar",
        "format": "nested",
        "auth": True,
    },
]


class DinarPoster:
    """
    هەر خولەکێک نرخی دۆلار بە دینار دەنێرێت.
    """

    def __init__(self, telegram: TelegramService):
        self.telegram = telegram
        self.config = Config()

    def _fetch_from_endpoint(
        self, url: str, response_format: str, use_auth: bool
    ) -> tuple[float | None, str | None]:
        headers = {}
        if use_auth:
            token = self.config.DINAR_API_TOKEN
            headers["Authorization"] = f"Bearer {token}"

        try:
            logger.info(f"🌐 DinarAPI request => {url}")
            response = requests.get(url, headers=headers, timeout=10)

            logger.info(
                f"📡 DinarAPI response status={response.status_code} url={response.url}"
            )

            if response.status_code != 200:
                logger.error(
                    f"DinarAPI status {response.status_code} body={response.text}"
                )
                return None, None

            data = response.json()
            logger.info(f"📦 DinarAPI response json={data}")

            if response_format == "flat":
                return data.get("value"), data.get("created_at")

            if response_format == "nested":
                inner = data.get("data", {})
                return inner.get("value"), inner.get("created_at")

            logger.error(f"Unknown response format: {response_format}")
            return None, None

        except Exception as e:
            logger.error(f"DinarAPI fetch error: {e}")
            return None, None

    def _fetch_dinar_price_sync(self) -> tuple[float | None, str | None]:
        for endpoint in DINAR_API_URLS:
            logger.info(f"🔎 Trying endpoint: {endpoint['name']}")

            value, created_at = self._fetch_from_endpoint(
                url=endpoint["url"],
                response_format=endpoint["format"],
                use_auth=endpoint["auth"],
            )

            if value:
                logger.info(f"✅ DinarAPI success via {endpoint['name']}")
                return value, created_at

        logger.warning("⚠️ DinarPoster: هەموو endpoint ـەکان fail بوون")
        return None, None

    async def _fetch_dinar_price(self) -> tuple[float | None, str | None]:
        return await asyncio.to_thread(self._fetch_dinar_price_sync)

    def build_message(self, value: float, now: datetime) -> str:
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%d/%m/%Y")
        channel = self.config.CHANNEL_USERNAME
        one_dollar = value / 100

        return (
            "💵 نرخی دۆلار بە دینار\n\n"
            f"💲 100 دۆلار = {value:,.0f} دینار\n"
            f"💲 1 دۆلار  = {one_dollar:,.0f} دینار\n\n"
            f"🕐 {time_str} | {date_str}\n"
            f"🔔 {channel}"
        )

    def _is_working_hours(self, now: datetime) -> bool:
        return True  # بۆ تاقیکردنەوە هەر کاتێک کار بکات

    async def post_dinar(self) -> None:
        try:
            logger.info("🚀 DinarPoster: دەچێت بۆ وەرگرتنی نرخ")
            value, created_at = await self._fetch_dinar_price()

            if not value:
                logger.warning("⚠️ DinarPoster: نرخ نەگەیشت")
                return

            now = datetime.now(self.config.BAGHDAD_TZ)
            msg = self.build_message(value, now)
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
            else:
                logger.info("🛌 DinarPoster: لە کاتی کارکردن نییە")

            await asyncio.sleep(60)
