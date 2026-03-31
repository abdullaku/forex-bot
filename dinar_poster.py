import asyncio
import logging
import re
from datetime import datetime

import requests

from config import Config
from telegram_service import TelegramService

logger = logging.getLogger(__name__)

DINAR_ENDPOINTS = [
    {
        "name": "nrxi-dolar-erbil",
        "url": "https://dinarapi.hediworks.site/api/v2/nrxi-dolar/erbil",
        "format": "nested",
        "auth": True,
    },
    {
        "name": "nrxi-dolar-hawler",
        "url": "https://dinarapi.hediworks.site/api/v2/nrxi-dolar/hawler",
        "format": "nested",
        "auth": True,
    },
    {
        "name": "get-price-erbil",
        "url": "https://dinarapi.hediworks.site/api/v2/get-price?id=5&location=erbil",
        "format": "flat",
        "auth": True,
    },
]

DINAR_HOME_URL = "https://dinarapi.hediworks.site"


class DinarPoster:
    def __init__(self, telegram: TelegramService):
        self.telegram = telegram
        self.config = Config()

    def _headers(self, with_auth: bool = True) -> dict:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
        }
        if with_auth:
            headers["Authorization"] = f"Bearer {self.config.DINAR_API_TOKEN}"
        return headers

    def _fetch_from_endpoint(
        self, name: str, url: str, response_format: str, use_auth: bool
    ) -> tuple[float | None, str | None]:
        try:
            response = requests.get(
                url,
                headers=self._headers(with_auth=use_auth),
                timeout=10,
            )

            if response.status_code != 200:
                logger.warning(f"❌ {name} failed: status={response.status_code}")
                return None, None

            data = response.json()

            if response_format == "flat":
                return data.get("value"), data.get("created_at")

            if response_format == "nested":
                inner = data.get("data", {})
                return inner.get("value"), inner.get("created_at")

            return None, None

        except Exception as e:
            logger.warning(f"❌ {name} error: {e}")
            return None, None

    def _try_scrape_homepage(self) -> tuple[float | None, str | None]:
        try:
            response = requests.get(
                DINAR_HOME_URL,
                headers=self._headers(with_auth=False),
                timeout=10,
            )

            if response.status_code != 200:
                logger.warning(f"❌ homepage scrape failed: status={response.status_code}")
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

            logger.warning("❌ homepage scrape failed: no price found")
            return None, None

        except Exception as e:
            logger.warning(f"❌ homepage scrape error: {e}")
            return None, None

    def _fetch_dinar_price_sync(self) -> tuple[float | None, str | None, str | None]:
        for endpoint in DINAR_ENDPOINTS:
            value, created_at = self._fetch_from_endpoint(
                endpoint["name"],
                endpoint["url"],
                endpoint["format"],
                endpoint["auth"],
            )
            if value:
                return value, created_at, endpoint["name"]

        logger.info("🔁 Falling back to homepage scrape")
        value, created_at = self._try_scrape_homepage()
        if value:
            return value, created_at, "homepage-scrape"

        return None, None, None

    async def _fetch_dinar_price(self) -> tuple[float | None, str | None, str | None]:
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
            value, created_at, source = await self._fetch_dinar_price()

            if not value:
                logger.warning("⚠️ DinarPoster: نرخ نەگەیشت")
                return

            now = datetime.now(self.config.BAGHDAD_TZ)
            msg = self.build_message(value, now, created_at)
            await self.telegram.send_message(msg)

            logger.info(
                f"✅ DinarPoster: 100$ = {value:,.0f} IQD | source={source} | created_at={created_at}"
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
