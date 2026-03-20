import asyncio
import logging
import os
from telegram import Bot
from sources import NewsScraper
from translator import translate_to_kurdish, generate_daily_analysis
from config import Config
from database import setup_db, is_posted, mark_posted, save_news, get_todays_news
from datetime import datetime, timezone, timedelta

from keep_alive import keep_alive
keep_alive()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BAGHDAD_TZ = timezone(timedelta(hours=3))

async def format_post(article):
    post = f"📰 <b>{article['title_ku']}</b>\n\n"
    post += f"{article['summary_ku']}\n\n"
    source_label = "🇮🇶 هەواڵی ناوەخۆ | Iraq Business News" if article['source'] == "Iraq Business News" else article['source']
    post += f"📌 {source_label}\n"
    post += f"🔗 <a href='{article['url']}'>بینە هەواڵەکە لە سەرچاوە</a>\n"
    post += f"🕐 {datetime.now(BAGHDAD_TZ).strftime('%H:%M | %d/%m/%Y')}"
    return post

def is_kurdish(text):
    kurdish_chars = set('ابتثجحخدذرزسشصضطظعغفقكلمنهوي\u06a9\u06af\u06c1\u06be\u0698\u0686\u06cc\u06d5\u06c6\u06c7\u06c8\u06cb\u06cf\u06b5\u06b1\u0695\u067e\u062c\u06a4')
    count = sum(1 for c in text if c in kurdish_chars)
    return count > len(text) * 0.2

async def run_bot():
    bot = Bot(token=Config.BOT_TOKEN)
    scraper = NewsScraper()
    await setup_db()
    logger.info("🤖 Forex Bot started with Deep Analysis and Keep-Alive!")
    
    last_calendar_day = ""
    last_wrap_day = ""

    while True:
        try:
            now = datetime.now(BAGHDAD_TZ)
            current_hour = now.hour
            current_day = now.strftime("%Y-%m-%d")

            if current_hour == 9 and last_calendar_day != current_day:
                calendar_events = await scraper.fetch_calendar()
                if calendar_events:
                    msg = "📅 <b>گرنگترین هەواڵە ئابوورییەکانی ئەمڕۆ:</b>\n\n" + "\n".join(calendar_events)
                    await bot.send_message(chat_id=Config.CHANNEL_ID, text=msg, parse_mode="HTML")
                    last_calendar_day = current_day

            if current_hour == 23 and last_wrap_day != current_day:
                todays_articles = await get_todays_news()
                if todays_articles:
                    analysis_text = await generate_daily_analysis(todays_articles)
                    await bot.send_message(chat_id=Config.CHANNEL_ID, text=analysis_text, parse_mode="HTML")
                    last_wrap_day = current_day
                    logger.info("✅ Deep Analysis posted.")

            articles = await scraper.fetch_all()
            for article in articles:
                clean_url = article['url'].split('?')[0].split('#')[0]
                if not await is_posted(clean_url):
                    await mark_posted(clean_url)
                    article['url'] = clean_url
                    article = await translate_to_kurdish(article)
                    if article.get('title_ku') and is_kurdish(article['title_ku']):
                        text = await format_post(article)
                        try:
                            if article.get('image_url'):
                                await bot.send_photo(chat_id=Config.CHANNEL_ID, photo=article['image_url'], caption=text, parse_mode="HTML")
                            else:
                                await bot.send_message(chat_id=Config.CHANNEL_ID, text=text, parse_mode="HTML", disable_web_page_preview=True)
                        except:
                            await bot.send_message(chat_id=Config.CHANNEL_ID, text=text, parse_mode="HTML", disable_web_page_preview=True)
                        await save_news(article)
                        await asyncio.sleep(Config.POST_DELAY_SECONDS)

            await asyncio.sleep(Config.CHECK_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(run_bot())
