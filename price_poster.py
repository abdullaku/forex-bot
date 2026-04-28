import asyncio
import logging
from datetime import datetime, timezone, timedelta

import aiohttp
import pytz

from config import Config
from telegram_service import TelegramService
from facebook import FacebookService

logger = logging.getLogger(__name__)

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"

LONDON_TZ   = pytz.timezone("Europe/London")
NEW_YORK_TZ = pytz.timezone("America/New_York")
TOKYO_TZ    = pytz.timezone("Asia/Tokyo")

SESSIONS = [
    {
        "id":      "asia",
        "name_ku": "سێشنی ئەسیا",
        "emoji":   "🌏",
        "tz":      TOKYO_TZ,
        "open_hour":   9,
        "open_minute": 0,
    },
    {
        "id":      "london",
        "name_ku": "سێشنی لەندەن",
        "emoji":   "🇬🇧",
        "tz":      LONDON_TZ,
        "open_hour":   8,
        "open_minute": 0,
    },
    {
        "id":      "newyork",
        "name_ku": "سێشنی نیویۆرک",
        "emoji":   "🇺🇸",
        "tz":      NEW_YORK_TZ,
        "open_hour":   9,
        "open_minute": 30,
    },
]

SESSION_TOLERANCE_MINUTES = 4


class PricePoster:
    GOLD_TICKER   = "GC=F"
    SILVER_TICKER = "SI=F"
    BRENT_TICKER  = "BZ=F"
    WTI_TICKER    = "CL=F"
    EURUSD_TICKER = "EURUSD=X"
    GBPUSD_TICKER = "GBPUSD=X"
    USDJPY_TICKER = "USDJPY=X"
    DXY_TICKER    = "DX-Y.NYB"
    SP500_TICKER  = "ES=F"
    DOW_TICKER    = "YM=F"
    BTC_TICKER    = "BTC-USD"

    ALL_TICKERS = [
        GOLD_TICKER, SILVER_TICKER,
        BRENT_TICKER, WTI_TICKER,
        EURUSD_TICKER, GBPUSD_TICKER, USDJPY_TICKER, DXY_TICKER,
        SP500_TICKER, DOW_TICKER,
        BTC_TICKER,
    ]

    def __init__(self, telegram: TelegramService, facebook: FacebookService):
        self.telegram = telegram
        self.facebook = facebook
        self.config   = Config()
        self._prev: dict[str, float | None] = {t: None for t in self.ALL_TICKERS}
        self._last_posted_session: str | None = None

    async def _fetch_price(self, symbol: str) -> float | None:
        url = YAHOO_URL.format(symbol=symbol)
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0"}
            ) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return data["chart"]["result"][0]["meta"].get("regularMarketPrice")
        except Exception as e:
            logger.error(f"Price fetch error {symbol}: {e}")
            return None

    async def get_prices(self) -> dict[str, float | None]:
        results = await asyncio.gather(*[self._fetch_price(t) for t in self.ALL_TICKERS])
        return dict(zip(self.ALL_TICKERS, results))

    @staticmethod
    def _arrow(cur: float | None, prev: float | None) -> str:
        if cur is None or prev is None:
            return "  "
        return " ⬆️" if cur > prev else (" ⬇️" if cur < prev else "  ")

    @staticmethod
    def _fmt(val: float | None, d: int = 2) -> str:
        return f"{val:,.{d}f}" if val is not None else "—"

    def _pct(self, cur: float | None, prev: float | None) -> str:
        if cur is None or prev is None or prev == 0:
            return ""
        pct = (cur - prev) / prev * 100
        sign = "+" if pct >= 0 else ""
        return f"({sign}{pct:.2f}%)"

    def build_message(self, prices: dict, now: datetime, session: dict) -> str:
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%d/%m/%Y")
        ch = self.config.CHANNEL_USERNAME
        p  = prices
        v  = self._prev

        def row(ticker, label, decimals=2):
            cur  = p[ticker]
            prev = v[ticker]
            ar   = self._arrow(cur, prev)
            pct  = self._pct(cur, prev)
            val  = self._fmt(cur, decimals)
            return f"  {label}  {val}{ar} {pct}\n"

        return (
            f"📊 {session['name_ku']} کرایەوە {session['emoji']}\n\n"

            f"🏅 Metals\n"
            + row(self.GOLD_TICKER,   "🥇 Gold    (XAU)", 2)
            + row(self.SILVER_TICKER, "🥈 Silver  (XAG)", 3)

            + f"\n🛢️ Oil\n"
            + row(self.BRENT_TICKER, "🛢 Brent  ", 2)
            + row(self.WTI_TICKER,   "🛢 WTI    ", 2)

            + f"\n💱 Forex\n"
            + row(self.EURUSD_TICKER, "🇪🇺 EUR/USD", 4)
            + row(self.GBPUSD_TICKER, "🇬🇧 GBP/USD", 4)
            + row(self.USDJPY_TICKER, "🇯🇵 USD/JPY", 3)
            + row(self.DXY_TICKER,    "💵 DXY    ", 3)

            + f"\n📈 Stock Market\n"
            + row(self.SP500_TICKER, "📊 S&P 500  ", 0)
            + row(self.DOW_TICKER,   "📉 Dow Jones", 0)

            + f"\n₿ Crypto\n"
            + row(self.BTC_TICKER, "₿ Bitcoin  ", 0)

            + f"\n🕐 {time_str}  |  {date_str}\n"
            f"🔔 {ch}"
        )

    def _active_opening_session(self, utc_now: datetime) -> dict | None:
        if utc_now.weekday() > 4:
            return None

        for s in SESSIONS:
            local_now = utc_now.astimezone(s["tz"])
            session_open = local_now.replace(
                hour=s["open_hour"], minute=s["open_minute"],
                second=0, microsecond=0,
            )
            diff_minutes = (local_now - session_open).total_seconds() / 60
            if 0 <= diff_minutes < SESSION_TOLERANCE_MINUTES:
                return s

        return None

    def _session_day_key(self, utc_now: datetime, session: dict) -> str:
        date_str = utc_now.strftime("%Y-%m-%d")
        return f"{date_str}_{session['id']}"

    async def post_prices(self, session: dict) -> None:
        try:
            prices = await self.get_prices()

            if not prices.get(self.GOLD_TICKER) or not prices.get(self.BRENT_TICKER):
                logger.warning("⚠️ PricePoster: نرخی سەرەکیەکان نەگەیشت")
                return

            now = datetime.now(self.config.BAGHDAD_TZ)
            msg = self.build_message(prices, now, session)

            try:
                await self.telegram.send_message(msg)
            except Exception as e:
                logger.error(f"❌ PricePoster Telegram: {e}")

            try:
                await self.facebook.post(msg)
            except Exception as e:
                logger.error(f"❌ PricePoster Facebook: {e}")

            for k, val in prices.items():
                if val is not None:
                    self._prev[k] = val

            gold  = prices[self.GOLD_TICKER]
            brent = prices[self.BRENT_TICKER]
            logger.info(
                f"✅ PricePoster | {session['name_ku']} | زێر={gold:.2f} برێنت={brent:.2f}"
            )

        except Exception as e:
            logger.error(f"❌ PricePoster error: {e}")

    async def run(self) -> None:
        logger.info("🕐 PricePoster: دەستی پێکرد")

        while True:
            await asyncio.sleep(20)

            utc_now = datetime.now(timezone.utc)
            session = self._active_opening_session(utc_now)

            if session is None:
                continue

            key = self._session_day_key(utc_now, session)

            if self._last_posted_session == key:
                continue

            self._last_posted_session = key
            logger.info(f"⏰ کرانەوەی سێشن: {session['name_ku']}")
            await self.post_prices(session)
