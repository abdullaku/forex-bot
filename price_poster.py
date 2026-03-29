import asyncio
import logging
from datetime import datetime

import aiohttp  # ✅ بەجێی yfinance

from config import Config
from telegram_service import TelegramService

logger = logging.getLogger(__name__)

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"


class PricePoster:
    """
    هەر ٣٠ خولەک نرخی زێر و نەوتی برێنت دەنێرێت بۆ چانێلی تێلیگرام.
    تەنیا دووشەمە تا هەینی، کاتژمێر ٩ بەیانی تا ١١ شەو (بەعقوبە UTC+3).
    """

    GOLD_TICKER = "GC=F"
    BRENT_TICKER = "BZ=F"

    def __init__(self, telegram: TelegramService):
        self.telegram = telegram
        self.config = Config()

    # ── وەرگرتنی نرخ ──────────────────────────────────────────────────────────

    async def _fetch_price(self, symbol: str) -> float | None:
        """✅ ڕاستەوخۆ لە Yahoo Finance — بێ yfinance"""
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

    # ── دروستکردنی پۆست ───────────────────────────────────────────────────────

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

    # ── مەرجی کات ─────────────────────────────────────────────────────────────

    def _is_market_time(self, now: datetime) -> bool:
        """
        دووشەمە (0) تا هەینی (4), کاتژمێر 9 بەیانی تا 11 شەو (تا کۆتا 23:30).
        """
        if now.weekday() > 4:          # شەممە و یەکشەممە
            return False
        if now.hour < 9 or now.hour >= 24:
            return False
        if now.hour == 23 and now.minute > 30:  # دوای 23:30 دیکە نەنێرێت
            return False
        return True

    # ── ناردنی پۆست ───────────────────────────────────────────────────────────

    async def post_prices(self) -> None:
        try:
            gold, brent = await self.get_prices()
            if not gold or not brent:
                logger.warning("⚠️ PricePoster: نرخەکان نەگەیشت")
                return

            now = datetime.now(self.config.BAGHDAD_TZ)
            msg = self.build_message(gold, brent, now)
            await self.telegram.send_message(msg)
            logger.info(f"✅ PricePoster: زێر={gold:.2f}  برێنت={brent:.2f}")

        except Exception as e:
            logger.error(f"❌ PricePoster error: {e}")

    # ── لووپی سەرەکی ──────────────────────────────────────────────────────────

    async def run(self) -> None:
        """
        چاوەڕوانی دەکات تا کاتژمێر :00 یان :30 بگاتەوە، ئەگەر کاتی بازاڕە دەنێرێت.
        """
        logger.info("🕐 PricePoster: دەستی پێکرد")

        while True:
            now = datetime.now(self.config.BAGHDAD_TZ)
            minute = now.minute
            second = now.second

            # چاوەڕوان بکە تا :00 یان :30ی داهاتوو
            if minute < 30:
                wait_seconds = (30 - minute) * 60 - second
            else:
                wait_seconds = (60 - minute) * 60 - second

            # کەمێک زیادتر بچووکبکەرەوە تا دڵنیا بین دقیقەکە تەواوبووە
            wait_seconds = max(wait_seconds, 1)
            await asyncio.sleep(wait_seconds)

            now = datetime.now(self.config.BAGHDAD_TZ)
            if self._is_market_time(now):
                await self.post_prices()
