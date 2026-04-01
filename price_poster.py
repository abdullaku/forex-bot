import asyncio
import logging
from datetime import datetime

import aiohttp

from config import Config
from telegram_service import TelegramService
from facebook import FacebookService

logger = logging.getLogger(__name__)

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"


class PricePoster:
    GOLD_TICKER = "GC=F"
    BRENT_TICKER = "BZ=F"

    def __init__(self, telegram: TelegramService, facebook: FacebookService):
        self.telegram = telegram
        self.facebook = facebook
        self.config = Config()

    async def _fetch_price(self, symbol: str) -> float | None:
        url = YAHOO_URL.format(symbol=symbol)
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return data["chart"]["result"][0]["meta"].get("regularMarketPrice")
        except Exception as e:
            logger.error(f"Price fetch error {symbol}: {e}")
            return None

    async def get_prices(self) -> tuple[float, float]:
        gold, brent = await asyncio.gather(
            self._fetch_price(self.GOLD_TICKER),
            self._fetch_price(self.BRENT_TICKER),
        )
        return gold, brent

    def build_message(self, gold: float, brent: float, now: datetime) -> str:
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%d/%m/%Y")
        channel = self.config.CHANNEL_USERNAME

        return (
            "💹 نرخی بازاڕی ئێستا\n\n"
            f"🥇 زێڕ (XAU/USD)\n"
            f"    💲 {gold:,.2f}\n\n"
            f"🛢️ نەوتی برێنت (Brent)\n"
            f"    💲 {brent:.2f}\n\n"
            f"🕐 {time_str} | {date_str}\n"
            f"🔔 {channel}"
        )

    def _is_market_time(self, now: datetime) -> bool:
        if now.weekday() > 4:
            return False
        if now.hour < 9 or now.hour >= 24:
            return False
        if now.hour == 23 and now.minute > 30:
            return False
        return True

    async def post_prices(self) -> None:
        try:
            gold, brent = await self.get_prices()
            if not gold or not brent:
                logger.warning("⚠️ PricePoster: نرخەکان نەگەیشت")
                return

            now = datetime.now(self.config.BAGHDAD_TZ)
            msg = self.build_message(gold, brent, now)

            try:
                await self.telegram.send_message(msg)
            except Exception as e:
                logger.error(f"❌ PricePoster Telegram error: {e}")

            try:
                await self.facebook.post(msg)
            except Exception as e:
                logger.error(f"❌ PricePoster Facebook error: {e}")

            logger.info(f"✅ PricePoster: زێر={gold:.2f}  برێنت={brent:.2f}")

        except Exception as e:
            logger.error(f"❌ PricePoster error: {e}")

    async def run(self) -> None:
        logger.info("🕐 PricePoster: دەستی پێکرد")
        while True:
            now = datetime.now(self.config.BAGHDAD_TZ)
            minute = now.minute
            second = now.second

            if minute < 30:
                wait_seconds = (30 - minute) * 60 - second
            else:
                wait_seconds = (60 - minute) * 60 - second

            wait_seconds = max(wait_seconds, 1)
            await asyncio.sleep(wait_seconds)

            now = datetime.now(self.config.BAGHDAD_TZ)
            if self._is_market_time(now):
                await self.post_prices()
