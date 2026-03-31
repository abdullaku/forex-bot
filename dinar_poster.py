import asyncio
import logging
import re
from datetime import datetime

import requests

from config import Config
from telegram_service import TelegramService

logger = logging.getLogger(__name__)

GET_PRICE_URL = "https://dinarapi.hediworks.site/api/v2/get-price?id=5&location=erbil"
NRXI_DOLAR_URL = "https://dinarapi.hediworks.site/api/v2/nrxi-dolar"
DINAR_HOME_URL = "https://dinarapi.hediworks.site"


class DinarPoster:
    """
    هەر خولەکێک نرخی 100 دۆلار بە دینار دەنێرێت.
    """

    def __init__(self, telegram: TelegramService):
        self.telegram = telegram
        self.config = Config()

    def _headers(self, with_auth: bool = True) -> dict:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
        }
        if with_auth:
            headers["Authorization"] = f"Bearer {self.config.DINAR_API_TOKEN}"
        return headers

    def _try_get_price(self) -> tuple[float | None, str | None]:
        try:
            logger.info(f"🌐 Trying get-price => {GET_PRICE_URL}")
            response = requests.get(
                GET_PRICE_URL,
                headers=self._headers(with_auth=True),
                timeout=10,
            )
            logger.info(f"📡 get-price status={response.status_code} url={response.url}")

            if response.status_code != 200:
                logger.error(f"get-price body={response.text}")
                return None, None

            data = response.json()
            logger.info(f"📦 get-price json={data}")
            return data.get("value"), data.get("created_at")

        except Exception as e:
            logger.error(f"get-price fetch error: {e}")
            return None, None

    def _try_nrxi_dolar(self) -> tuple[float | None, str | None]:
        try:
            logger.info(f"🌐 Trying nrxi-dolar => {NRXI_DOLAR_URL}")
            response = requests.get(
                NRXI_DOLAR_URL,
                headers=self._headers(with_auth=True),
                timeout=10,
            )
            logger.info(f"📡 nrxi-dolar status={response.status_code} url={response.url}")

            if response.status_code != 200:
                logger.error(f"nrxi-dolar body={response.text}")
                return None, None

            data = response.json()
            logger.info(f"📦 nrxi-dolar json={data}")
            inner = data.get("data", {})
            return inner.get("value"), inner.get("created_at")

        except Exception as e:
            logger.error(f"nrxi-dolar fetch error: {e}")
            return None, None

    def _try_scrape_homepage(self) -> tuple[float | None, str | None]:
        try:
            logger.info(f"🌐 Trying homepage scrape => {DINAR_HOME_URL}")
            response = requests.get(
                DINAR_HOME_URL,
                headers=self._headers(with_auth=False),
                timeout=10,
            )
            logger.info(f"📡 homepage status={response.status_code} url={response.url}")

            if response.status_code != 200:
                logger.error(f"homepage body={response.text[:500]}")
                return None, None

            html = response.text

            # هەوڵی یەکەم: JSON demo block ی nrxi-dolar
            m = re.search(
                r'"data"\s*:\s*\{\s*"value"\s*:\s*"?([\d,]+)"?\s*,\s*"created_at"\s*:\s*"([^"]+)"',
                html,
                re.S,
            )
            if m:
                value = float(m.group(1).replace(",", ""))
                created_at = m.group(2)
                logger.info(f"✅ homepage scrape success via json block: value={value}")
                return value, created_at

            # هەوڵی دووەم: دەقی 100 دۆلار
            m2 = re.search(r'100\s*دۆلار\s*.*?([\d,]{3,})', html, re.S)
            if m2:
                value = float(m2.group(1).replace(",", ""))
                logger.info(f"✅ homepage scrape success via text block: value={value}")
                return value, None

            logger.error("homepage scrape failed: could not find dollar price")
            return None, None

        except Exception as e:
            logger.error(f"homepage scrape error: {e}")
            return None, None

    def _fetch_dinar_price_sync(self) -> tuple[float | None, str | None]:
        value, created_at = self._try_get_price()
        if value:
            logger.info("✅ Success via get-price")
            return value, created_at

        value, created_at = self._try_nrxi_dolar()
        if value:
            logger.info("✅ Success via nrxi-dolar")
            return value, created_at

        value, created_at = self._try_scrape_homepage()
        if value:
            logger.info("✅ Success via homepage scrape")
            return value, created_at

        logger.warning("⚠️ DinarPoster: هەموو ڕێگاکان fail بوون")
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
            f"💲 1 دۆلار  = {one_dollar:,.0f} دینار\n"
            f"{freshness}\n\n"
            f"🕐 {time_str} | {date_str}\n"
            f"🔔 {channel}"
        )

    def _is_working_hours(self, now: datetime) -> bool:
        return True  # بۆ تاقیکردنەوە

    async def post_dinar(self) -> None:
        try:
            logger.info("🚀 DinarPoster: دەچێت بۆ وەرگرتنی نرخ")
            value, created_at = await self._fetch_dinar_price()

            if not value:
                logger.warning("⚠️ DinarPoster: نرخ نەگەیشت")
                return

            now = datetime.now(self.config.BAGHDAD_TZ)
            msg = self.build_message(value, now, created_at)
            await self.telegram.send_message(msg)
            logger.info(f"✅ DinarPoster: 100$ = {value:,.0f} IQD | created_at={created_at}")

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
