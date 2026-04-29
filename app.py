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
from economic_calendar import CalendarService

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

        self.price_poster = PricePoster(self.telegram, self.facebook)
        self.dinar_poster = DinarPoster(self.telegram, self.facebook)
        self.support_bot = SupportBot(token=self.config.SUPPORT_TOKEN)
        self.calendar = CalendarService(
            send_callback=self.telegram.send_message,
            fb_callback=self.facebook.post,
        )

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
        logger.info("🚀 Bot Started - Official macro news + FXStreet market news")

    async def _calendar_loop(self) -> None:
        while True:
            try:
                await self.calendar.tick()
            except Exception as e:
                logger.error(f"Calendar tick error: {e}")
            await asyncio.sleep(30)

    async def process_article(
        self,
        article: dict,
        current_time: str,
        current_date: str,
    ) -> str:
        url = (article.get("url") or "").split("?")[0].strip()

        if not url:
            logger.warning("Article skipped because URL is missing")
            return "missing_url"

        title = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        source = article.get("source", "Official Source")
        currency = article.get("currency", "")

        if await is_posted(url):
            logger.info(f"News already posted: {source} - {title[:70] or url}")
            return "already_posted"

        if not title:
            logger.warning(f"Article skipped because title is missing: {url}")
            await mark_posted(url)
            return "missing_title"

        text = await process_smart_news(
            title=title,
            description=summary,
            source=source,
            currency=currency,
        )

        if not text:
            logger.warning(
                f"Formatting failed, will retry later: {source} - {title[:70]}"
            )
            return "format_failed"

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
            logger.info(f"Telegram posted: {source} - {title[:70]}")
        except Exception as e:
            logger.error(f"Telegram error: {type(e).__name__}: {e}")

        try:
            await self.facebook.post(
                text=facebook_msg,
                image_url=article.get("image_url"),
                link_url=url,
            )
            fb_ok = True
            logger.info(f"Facebook posted: {source} - {title[:70]}")
        except Exception as e:
            logger.error(f"Facebook error: {type(e).__name__}: {e}")

        if tg_ok or fb_ok:
            await mark_posted(url)
            return "posted"

        logger.warning(
            f"News send failed on all channels, will retry later: {source} - {title[:70]}"
        )
        return "send_failed"

    async def process_news(self, current_time: str, current_date: str) -> None:
        articles = await self.scraper.fetch_all()

        if not articles:
            logger.info("No news found from official sources or FXStreet")
            return

        logger.info(f"Found {len(articles)} news items")

        stats = {
            "posted": 0,
            "already_posted": 0,
            "format_failed": 0,
            "send_failed": 0,
            "missing_url": 0,
            "missing_title": 0,
        }

        for article in articles:
            status = await self.process_article(
                article=article,
                current_time=current_time,
                current_date=current_date,
            )

            stats[status] = stats.get(status, 0) + 1

            if status == "posted":
                await asyncio.sleep(self.config.POST_DELAY)

        logger.info(
            "News summary: "
            f"posted={stats.get('posted', 0)} | "
            f"already_posted={stats.get('already_posted', 0)} | "
            f"format_failed={stats.get('format_failed', 0)} | "
            f"send_failed={stats.get('send_failed', 0)} | "
            f"missing_url={stats.get('missing_url', 0)} | "
            f"missing_title={stats.get('missing_title', 0)}"
        )

    async def run(self) -> None:
        await self.setup()

        asyncio.create_task(self.price_poster.run())
        asyncio.create_task(self.dinar_poster.run())
        asyncio.create_task(self._calendar_loop())

        while True:
            try:
                now, current_time, current_date = self.get_time_strings()

                await self.process_news(
                    current_time=current_time,
                    current_date=current_date,
                )

                await asyncio.sleep(self.config.CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"Error: {type(e).__name__}: {e}")
                await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(ForexBotApp().run())
