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

logger = logging.getLogger(__name__)


class ForexBotApp:
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
        self.last_calendar_day = ""
        self.price_poster = PricePoster(self.telegram, self.facebook)
        self.dinar_poster = DinarPoster(self.telegram)

    def get_now(self) -> datetime:
        return datetime.now(self.config.BAGHDAD_TZ)

    def get_time_strings(self):
        now = self.get_now()
        current_day = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%d/%m/%Y")
        return now, current_day, current_time, current_date

    async def setup(self) -> None:
        await setup_db()
        logger.info("🚀 Bot Started")

    async def process_calendar(self, now: datetime, current_day: str) -> None:
        if now.hour == 9 and self.last_calendar_day != current_day:
            events = await self.scraper.fetch_calendar()

            if events:
                tg_msg = self.scraper.calendar_service.build_telegram_msg(events)
                fb_msg = self.scraper.calendar_service.build_facebook_msg(events)
                await self.telegram.send_message(tg_msg)
                await self.facebook.post(fb_msg)

            self.last_calendar_day = current_day

    async def process_article(
        self,
        article: dict,
        current_time: str,
        current_date: str,
    ) -> None:
        url = article["url"].split("?")[0]

        if await is_posted(url):
            return

        text = await process_smart_news(article["title"], article.get("summary", ""))

        if not text:
            await mark_posted(url)
            return

        source = article.get("source", "News")

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
        except Exception as e:
            logger.error(f"Telegram error: {e}")

        try:
            await self.facebook.post(
                text=facebook_msg,
                image_url=article.get("image_url"),
                link_url=url,
            )
            fb_ok = True
        except Exception as e:
            logger.error(f"Facebook error: {e}")

        if tg_ok or fb_ok:
            await mark_posted(url)

        await asyncio.sleep(self.config.POST_DELAY)

    async def process_news(self, current_time: str, current_date: str) -> None:
        articles = await self.scraper.fetch_all()

        for article in articles:
            await self.process_article(
                article=article,
                current_time=current_time,
                current_date=current_date,
            )

    async def run(self) -> None:
        await self.setup()

        asyncio.create_task(self.price_poster.run())
        asyncio.create_task(self.dinar_poster.run())

        while True:
            try:
                now, current_day, current_time, current_date = self.get_time_strings()

                await self.process_calendar(now, current_day)
                await self.process_news(current_time, current_date)

                await asyncio.sleep(self.config.CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(60)
