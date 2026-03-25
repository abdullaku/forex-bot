import os
import asyncio
import logging
import requests
import threading
import time
from telegram import Bot
from sources import NewsScraper
from translator import process_smart_news, generate_daily_analysis
from database import setup_db, is_posted, mark_posted, save_news, get_todays_news
from datetime import datetime, timezone, timedelta
from keep_alive import keep_alive

# --- ڕێکخستنی سەرەتایی ---
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8611761761:AAEU_XJjV8QQ3LPr2rWf6gDBNnH2TVbs3_E")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", -1003829360084))
FACEBOOK_PAGE_TOKEN = os.environ.get("FACEBOOK_PAGE_TOKEN", "EAAUuD0sVsdcBRB2vlTc2M8RPkPJWQY50ako6WZBLBA2G0lLZCgttUed0GYIFV0jRFRsOk8A9Py1MMvrfL9RP39vSW9hHaENjKQZAxM9nlOFZAbh8foqiBmQGhz7nH2T2dqwgCs9SPdV3cSs8HEA2UlWWnmYDyO3eZCqjvekyAVseZA552tRTQn5CHr2IYzyr1Kzb5ZCpYsV")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID", "994664793738553")

CHECK_INTERVAL = 300 
POST_DELAY = 10     

BAGHDAD_TZ = timezone(timedelta(hours=3))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_pinging():
    time.sleep(15)
    while True:
        try:
            requests.get("https://forex-bot-dq8f.onrender.com", timeout=15)
            logger.info("♻️ Self-ping: Active")
        except: pass
        time.sleep(300)

def post_to_facebook(text, image_url=None, link_url=None):
    import re
    clean_text = re.sub(r'<[^>]+>', '', text).strip()
    try:
        url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed"
        data = {"message": clean_text, "access_token": FACEBOOK_PAGE_TOKEN}
        if image_url:
            url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/photos"
            data = {"url": image_url, "caption": clean_text, "access_token": FACEBOOK_PAGE_TOKEN}
        elif link_url:
            data["link"] = link_url
        requests.post(url, data=data)
    except Exception as e:
        logger.error(f"❌ FB Error: {e}")

async def run_bot():
    bot = Bot(token=TOKEN)
    scraper = NewsScraper()
    await setup_db()
    logger.info("🚀 Forex Kurdistan Bot is LIVE!")
    
    last_calendar_day = ""

    while True:
        try:
            now = datetime.now(BAGHDAD_TZ)
            current_day = now.strftime("%Y-%m-%d")
            # کاتی ئێستای بەغدا بۆ ناو پۆستەکە
            current_time_str = now.strftime("%H:%M") 
            current_date_str = now.strftime("%d/%m/%Y")

            # ١. پۆستی کاڵێندەر (کاتژمێر ٩ی بەیانی)
            if now.hour == 9 and last_calendar_day != current_day:
                calendar_events = await scraper.fetch_calendar()
                if calendar_events:
                    msg = "📅 **ڕۆژژمێری ئابووری ئەمڕۆ**\n\n" + "\n".join(calendar_events)
                    await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode="HTML")
                    post_to_facebook(msg)
                last_calendar_day = current_day

            # ٢. پۆستی هەواڵە نوێیەکان بە دیکۆری تایبەت
            articles = await scraper.fetch_all()
            for article in articles:
                url = article['url'].split('?')[0]
                if not await is_posted(url):
                    kurdish_text = await process_smart_news(article['title'])
                    if kurdish_text:
                        await mark_posted(url)
                        
                        # --- لێرەدا دیکۆری پۆستەکە ڕێکدەخەینەوە ---
                        source_name = article.get('source', 'Bloomberg Quicktake')
                        
                        post_msg = (
                            f"📰 <b>{kurdish_text}</b>\n\n"
                            f"📌 {source_name}\n"
                            f"🔗 <a href='{url}'>بینە هەواڵەکە لە سەرچاوە</a>\n"
                            f"🕐 {current_time_str} | {current_date_str}\n\n"
                            f"🆔 @KURD_TRADER"
                        )
                        # ---------------------------------------

                        if article.get('image_url'):
                            await bot.send_photo(chat_id=CHANNEL_ID, photo=article['image_url'], caption=post_msg, parse_mode="HTML")
                        else:
                            await bot.send_message(chat_id=CHANNEL_ID, text=post_msg, parse_mode="HTML", disable_web_page_preview=True)

                        post_to_facebook(post_msg, image_url=article.get('image_url'), link_url=url)
                        await asyncio.sleep(POST_DELAY)
                    else:
                        await mark_posted(url)

            await asyncio.sleep(CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"Main loop error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=start_pinging, daemon=True).start()
    asyncio.run(run_bot())
