import os
import re
import html
import asyncio
import logging
import requests
from datetime import datetime, timezone, timedelta

from telegram import Bot
from sources import NewsScraper
from translator import process_smart_news
from database import setup_db, is_posted, mark_posted


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Config:
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
    FACEBOOK_PAGE_TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN")
    FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")

    CHECK_INTERVAL = 300
    POST_DELAY = 10
    BAGHDAD_TZ = timezone(timedelta(hours=3))


class TextFormatter:
    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""

        text = text.strip()

        # markdown / symbols cleanup
        text = text.replace("**", "")
        text = text.replace("__", "")
        text = text.replace("```", "")
        text = text.replace("##", "")
        text = text.replace("*", "")

        # normalize spaces/newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)

        return text.strip()

    @staticmethod
    def build_telegram_message(
        text: str,
        source: str,
        url: str,
        current_time: str,
        current_date: str,
    ) -> str:
        clean = TextFormatter.clean_text(text)
        safe_text = html.escape(clean)
        safe_source = html.escape(source)
        safe_url = html.escape(url, quote=True)

        return (
            f"📰 {safe_text}\n\n"
            f"📌 {safe_source}\n"
            f"🔗 <a href='{safe_url}'>بینە هەواڵەکە لە سەرچاوە</a>\n"
            f"🕐 {current_time} | {current_date}"
        )

    @staticmethod
    def build_facebook_message(
        text: str,
        source: str,
        current_time: str,
        current_date: str,
    ) -> str:
        clean = TextFormatter.clean_text(text)

        return (
            f"📰 {clean}\n\n"
            f"📌 {source}\n"
            f"🕐 {current_time} | {current_date}"
        )


class FacebookService:
    def __init__(self, page_id: str, page_token: str):
        self.page_id = page_id
        self.page_token = page_token

    def post(self, text: str, image_url: str = None, link_url: str = None) -> None:
        try:
            clean = TextFormatter.clean_text(text)

            # گرنگ: لە Facebook لینکەکە لە ناو دەق مەهێڵە
            clean = re.sub(r"🔗.*", "", clean).strip()
            clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

            if link_url:
                url = f"https://graph.facebook.com/v19.0/{self.page_id}/feed"
                data = {
                    "message": clean,
                    "link": link_url,
                    "access_token": self.page_token,
                }
            elif image_url:
                url = f"https://graph.facebook.com/v19.0/{self.page_id}/photos"
                data = {
                    "url": image_url,
                    "caption": clean,
                    "access_token": self.page_token,
                }
            else:
                url = f"https://graph.facebook.com/v19.0/{self.page_id}/feed"
                data = {
                    "message": clean,
                    "access_token": self.page_token,
                }

            requests.post(url, data=data, timeout=30)

        except Exception as e:
            logger.error(f"FB Error: {e}")


class TelegramService:
    def __init__(self, token: str, channel_id: int):
        self.bot = Bot(token=token)
        self.channel_id = channel_id

    async def send_message(self, text: str) -> None:
        await self.bot.send_message(
            chat_id=self.channel_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    async def send_photo(self, photo_url: str, caption: str) -> None:
        await self.bot.send_photo(
            chat_id=self.channel_id,
            photo=photo_url,
            caption=caption[:1024],
            parse_mode="HTML",
        )

    async def send_news(self, text: str, image_url: str = None) -> None:
        if image_url:
            await self.send_photo(image_url, text)
        else:
            await self.send_message(text)


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
        self.scraper = NewsScraper()
        self.last_calendar_day = ""

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
                msg = "📅 <b>ڕۆژژمێری ئابووری ئەمڕۆ</b>\n\n" + "\n".join(events)

                await self.telegram.send_message(msg)
                self.facebook.post(TextFormatter.clean_text(msg))

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

        text = await process_smart_news(article["title"])

        if not text:
            await mark_posted(url)
            return

        await mark_posted(url)

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

        await self.telegram.send_news(
            text=telegram_msg,
            image_url=article.get("image_url"),
        )

        self.facebook.post(
            text=facebook_msg,
            image_url=article.get("image_url"),
            link_url=url,
        )

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

        while True:
            try:
                now, current_day, current_time, current_date = self.get_time_strings()

                await self.process_calendar(now, current_day)
                await self.process_news(current_time, current_date)

                await asyncio.sleep(self.config.CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(60)


async def main():
    app = ForexBotApp()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
