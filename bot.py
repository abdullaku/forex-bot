import os
import re
import html
import asyncio
import logging
import requests
from telegram import Bot
from sources import NewsScraper
from translator import process_smart_news
from database import setup_db, is_posted, mark_posted
from datetime import datetime, timezone, timedelta

# ENV
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
FACEBOOK_PAGE_TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")

CHECK_INTERVAL = 300
POST_DELAY = 10

BAGHDAD_TZ = timezone(timedelta(hours=3))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_text(text):
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


def build_telegram_message(text, source, url, current_time, current_date):
    clean = clean_text(text)
    safe_text = html.escape(clean)
    safe_source = html.escape(source)
    safe_url = html.escape(url, quote=True)

    return (
        f"📰 {safe_text}\n\n"
        f"📌 {safe_source}\n"
        f"🔗 <a href='{safe_url}'>بینە هەواڵەکە لە سەرچاوە</a>\n"
        f"🕐 {current_time} | {current_date}"
    )


def build_facebook_message(text, source, url, current_time, current_date):
    clean = clean_text(text)

    return (
        f"📰 {clean}\n\n"
        f"📌 {source}\n"
        f"🔗 بینە هەواڵەکە لە سەرچاوە\n"
        f"{url}\n"
        f"🕐 {current_time} | {current_date}"
    )


def post_to_facebook(text, image_url=None, link_url=None):
    try:
        url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed"
        data = {"message": text, "access_token": FACEBOOK_PAGE_TOKEN}

        if image_url:
            url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/photos"
            data = {"url": image_url, "caption": text, "access_token": FACEBOOK_PAGE_TOKEN}

        elif link_url:
            data["link"] = link_url

        requests.post(url, data=data, timeout=30)

    except Exception as e:
        logger.error(f"FB Error: {e}")


async def run_bot():
    bot = Bot(token=TOKEN)
    scraper = NewsScraper()
    await setup_db()

    logger.info("🚀 Bot Started")

    last_calendar_day = ""

    while True:
        try:
            now = datetime.now(BAGHDAD_TZ)
            current_day = now.strftime("%Y-%m-%d")
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%d/%m/%Y")

            # 📅 Calendar
            if now.hour == 9 and last_calendar_day != current_day:
                events = await scraper.fetch_calendar()
                if events:
                    msg = "📅 <b>ڕۆژژمێری ئابووری ئەمڕۆ</b>\n\n" + "\n".join(events)
                    await bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=msg,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    post_to_facebook(clean_text(msg))

                last_calendar_day = current_day

            # 📰 News
            articles = await scraper.fetch_all()

            for article in articles:
                url = article["url"].split("?")[0]

                if not await is_posted(url):
                    text = await process_smart_news(article["title"])

                    if text:
                        await mark_posted(url)

                        source = article.get("source", "News")

                        telegram_msg = build_telegram_message(
                            text=text,
                            source=source,
                            url=url,
                            current_time=current_time,
                            current_date=current_date
                        )

                        facebook_msg = build_facebook_message(
                            text=text,
                            source=source,
                            url=url,
                            current_time=current_time,
                            current_date=current_date
                        )

                        if article.get("image_url"):
                            await bot.send_photo(
                                chat_id=CHANNEL_ID,
                                photo=article["image_url"],
                                caption=telegram_msg[:1024],
                                parse_mode="HTML"
                            )
                        else:
                            await bot.send_message(
                                chat_id=CHANNEL_ID,
                                text=telegram_msg,
                                parse_mode="HTML",
                                disable_web_page_preview=True
                            )

                        post_to_facebook(
                            facebook_msg,
                            image_url=article.get("image_url"),
                            link_url=url
                        )

                        await asyncio.sleep(POST_DELAY)

                    else:
                        await mark_posted(url)

            await asyncio.sleep(CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run_bot())
