import asyncio
import logging
from datetime import datetime

from manager import SourcesManager
from translator import process_smart_news
from database import setup_db, is_posted, mark_posted

from config import Config
from formatter import TextFormatter
from telegram_service import TelegramService
from facebook import FacebookService
from price_poster import PricePoster
from dinar_poster import DinarPoster
from support_bot import SupportBot

logger = logging.getLogger(__name__)


class ForexBotApp:
    """
    Main bot app.

    News behavior:
    - Only official macro/Forex sources are fetched through news.py.
    - No ForexFactory calendar.
    - No CNBC/Bloomberg/Fox/Iraq Business News.
    - No AI filtering.
    - AI only formats/translates official news.
    """

    def __init__(self):
        self.config = Config()

        self.telegram = TelegramService(
            token=self.config.TOKEN,
            channel_id=self.config.CHANNEL_ID,
        )

        self.facebook = FacebookService(
            page_id=self.config.FACEBOOK_PAGE_ID,
            page_token=self.config.FACEBOOK_PAGE_TOKEN,
        )

        self.scraper = SourcesManager()

        self.price_poster = PricePoster(self.telegram, self.facebook)
        self.dinar_poster = DinarPoster(self.telegram, self.facebook)
        self.support_bot = SupportBot(token=self.config.SUPPORT_TOKEN)

    def get_now(self) -> datetime:
        return datetime.now(self.config.BAGHDAD_TZ)

    def get_time_strings(self):
        now = self.get_now()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%d/%m/%Y")
        return now, current_time, current_date

    async def setup(self) -> None:
        await setup_db()
        await self.support_bot.start()
        logger.info("🚀 Bot Started - Official macro news only")

    async def process_article(
        self,
        article: dict,
        current_time: str,
        current_date: str,
    ) -> None:
        url = (article.get("url") or "").split("?")[0].strip()

        if not url:
            logger.warning("⚠️ Article skipped because URL is missing")
            return

        if await is_posted(url):
            return

        title = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        source = article.get("source", "Official Source")
        currency = article.get("currency", "")

        if not title:
            logger.warning(f"⚠️ Article skipped because title is missing: {url}")
            await mark_posted(url)
            return

        text = await process_smart_news(
            title=title,
            description=summary,
            source=source,
            currency=currency,
        )

        if not text:
            logger.info(f"⚠️ Formatting failed, marked as seen: {url}")
            await mark_posted(url)
            return

        telegram_msg = TextFormatter.build_telegram_message(
            text=text,
            source=source,
            url=url,
            current_time=current_time,
            current_date=current_date,
        )

        facebook_msg = TextFormatter.build_facebook_message(
            text=text,
            source=source,
            current_time=current_time,
            current_date=current_date,
        )

        tg_ok = False
        fb_ok = False

        try:
            await self.telegram.send_news(
                text=telegram_msg,
                image_url=article.get("image_url"),
            )
            tg_ok = True
            logger.info(f"✅ Telegram posted: {source} - {title[:70]}")
        except Exception as e:
            logger.error(f"Telegram error: {e}")

        try:
            await self.facebook.post(
                text=facebook_msg,
                image_url=article.get("image_url"),
                link_url=url,
            )
            fb_ok = True
            logger.info(f"✅ Facebook posted: {source} - {title[:70]}")
        except Exception as e:
            logger.error(f"Facebook error: {e}")

        if tg_ok or fb_ok:
            await mark_posted(url)

    async def process_news(self, current_time: str, current_date: str) -> None:
        articles = await self.scraper.fetch_all()

        if not articles:
            logger.info("ℹ️ No new official news found")
            return

        logger.info(f"📰 Found {len(articles)} official news items")

        for article in articles:
            await self.process_article(
                article=article,
                current_time=current_time,
                current_date=current_date,
            )

            await asyncio.sleep(self.config.POST_DELAY)

    async def run(self) -> None:
        await self.setup()

        asyncio.create_task(self.price_poster.run())
        asyncio.create_task(self.dinar_poster.run())

        while True:
            try:
                _, current_time, current_date = self.get_time_strings()

                await self.process_news(
                    current_time=current_time,
                    current_date=current_date,
                )

                await asyncio.sleep(self.config.CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(ForexBotApp().run())
