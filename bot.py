import asyncio
import logging
import requests
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from sources import NewsScraper
from translator import process_smart_news, generate_daily_analysis
from config import Config
from database import setup_db, is_posted, mark_posted, save_news, get_todays_news
from datetime import datetime, timezone, timedelta

from keep_alive import keep_alive
keep_alive()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BAGHDAD_TZ = timezone(timedelta(hours=3))

# تۆکنی نوێی تێلەگرام بۆ @ForexKurdistan_bot (گۆڕدرا)
FB_BOT_TOKEN = "8611761761:AAEU_XJjV8QQ3LPr2rWf6gDBNnH2TVbs3_E"
FB_CHANNEL_ID = -1003829360084

# زانیارییەکانی فەیسبووک (وەک خۆی هێڵراوەتەوە)
FACEBOOK_PAGE_TOKEN = "EAAUuD0sVsdcBRB2vlTc2M8RPkPJWQY50ako6WZBLBA2G0lLZCgttUed0GYIFV0jRFRsOk8A9Py1MMvrfL9RP39vSW9hHaENjKQZAxM9nlOFZAbh8foqiBmQGhz7nH2T2dqwgCs9SPdV3cSs8HEA2UlWWnmYDyO3eZCqjvekyAVseZA552tRTQn5CHr2IYzyr1Kzb5ZCpYsV"
FACEBOOK_PAGE_ID = "994664793738553"

def post_to_facebook(text, image_url=None, link_url=None):
    import re
    if not link_url:
        href_match = re.search(r"href=['\"]([^'\"]+)['\"]", text)
        if href_match:
            link_url = href_match.group(1)
    
    clean_text = re.sub(r'<[^>]+>', '', text)
    clean_text = re.sub(r'🔗.*\n?', '', clean_text).strip()
    
    if not link_url:
        urls = re.findall(r'https?://\S+', clean_text)
        if urls:
            link_url = urls[0]
            
    try:
        if image_url:
            url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/photos"
            caption = clean_text
            if link_url:
                caption += f"\n\n{link_url}"
            data = {"url": image_url, "caption": caption, "access_token": FACEBOOK_PAGE_TOKEN}
        elif link_url:
            url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed"
            data = {"message": clean_text, "link": link_url, "access_token": FACEBOOK_PAGE_TOKEN}
        else:
            url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed"
            data = {"message": clean_text, "access_token": FACEBOOK_PAGE_TOKEN}
            
        resp = requests.post(url, data=data)
        result = resp.json()
        if "id" in result:
            logger.info("✅ فەیسبووک: پۆست کرا")
        else:
            logger.error(f"❌ فەیسبووک: {result}")
    except Exception as e:
        logger.error(f"❌ هەڵەی فەیسبووک: {e}")

async def format_post(kurdish_text, article_url):
    post = f"📢 <b>هەواڵی ئابووری و فۆرێکس</b>\n\n"
    post += f"{kurdish_text}\n\n"
    post += f"🔗 <a href='{article_url}'>سەرچاوەی هەواڵ</a>\n"
    post += f"🕐 {datetime.now(BAGHDAD_TZ).strftime('%H:%M | %d/%m/%Y')}"
    return post

async def check_calendar_alerts(bot, alerted_events, posted_results):
    try:
        import aiohttp
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()
        now = datetime.now(BAGHDAD_TZ)
        today = now.strftime('%Y-%m-%d')
        for event in data:
            if today not in event.get('date', ''):
                continue
            if event.get('impact') != 'High':
                continue
            event_id = f"{event.get('date')}_{event.get('title')}_{event.get('currency')}"
            event_time_str = event.get('date', '')
            if 'T' not in event_time_str:
                continue
            event_dt = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
            event_dt_baghdad = event_dt.astimezone(BAGHDAD_TZ)
            diff_minutes = (event_dt_baghdad - now).total_seconds() / 60
            currency = event.get('currency', '')
            title = event.get('title', '')
            forecast = event.get('forecast', 'نادیارە')
            previous = event.get('previous', 'نادیارە')
            actual = event.get('actual', None)
            
            if actual and event_id not in posted_results:
                posted_results.add(event_id)
                try:
                    act_val = float(actual.replace('%', '').replace('K', '').replace('M', '').replace('B', ''))
                    fore_val = float(forecast.replace('%', '').replace('K', '').replace('M', '').replace('B', ''))
                    result_emoji = "✅ زیاتر — ئەرێنی" if act_val > fore_val else "❌ کەمتر — نەرێنی" if act_val < fore_val else "➡️ وەک پێشبینی"
                except:
                    result_emoji = "📊"
                
                msg = f"🔴 <b>ئەنجامی هەواڵی گرنگ</b>\n\n🏛 {title} | {currency}\n\n▪️ پێشوو: {previous}\n▪️ پێشبینی: {forecast}\n▫️ ئەنجام: <b>{actual}</b>\n\n{result_emoji}\n\n🕐 {now.strftime('%H:%M | %d/%m/%Y')}"
                await bot.send_message(chat_id=Config.CHANNEL_ID, text=msg, parse_mode="HTML")
                post_to_facebook(msg)
                
            elif not actual and 45 <= diff_minutes <= 75 and event_id not in alerted_events:
                alerted_events.add(event_id)
                msg = f"⚠️ <b>ئاگادارکردنەوە — دوای ١ کاتژمێر</b>\n\n🔴 {title} | {currency}\n\n▪️ پێشوو: {previous}\n▪️ پێشبینی: {forecast}\n\n⏰ کات: {event_dt_baghdad.strftime('%H:%M')}\n🕐 {now.strftime('%H:%M | %d/%m/%Y')}"
                await bot.send_message(chat_id=Config.CHANNEL_ID, text=msg, parse_mode="HTML")
                post_to_facebook(msg)

    except Exception as e:
        logger.error(f"Calendar alert error: {e}")

async def run_bot():
    # گرنگ: بەکارهێنانی تۆکنە نوێیەکە لێرەدا
    bot = Bot(token=FB_BOT_TOKEN)
    scraper = NewsScraper()
    await setup_db()
    logger.info("🤖 Forex Kurdistan Bot started with NEW Token!")
    
    last_calendar_day = ""
    last_wrap_day = ""
    alerted_events = set()
    posted_results = set()
    
    while True:
        try:
            now = datetime.now(BAGHDAD_TZ)
            current_hour = now.hour
            current_day = now.strftime("%Y-%m-%d")

            if current_hour == 9 and last_calendar_day != current_day:
                calendar_events = await scraper.fetch_calendar()
                if calendar_events:
                    msg = "\n".join(calendar_events)
                    await bot.send_message(chat_id=Config.CHANNEL_ID, text=msg, parse_mode="HTML")
                    post_to_facebook(msg)
                last_calendar_day = current_day

            await check_calendar_alerts(bot, alerted_events, posted_results)

            if current_hour >= 22 and last_wrap_day != current_day:
                todays_articles = await get_todays_news()
                if todays_articles:
                    analysis_text = await generate_daily_analysis(todays_articles)
                    if analysis_text:
                        await bot.send_message(chat_id=Config.CHANNEL_ID, text=analysis_text, parse_mode="HTML")
                        post_to_facebook(analysis_text)
                last_wrap_day = current_day

            articles = await scraper.fetch_all()
            for article in articles:
                clean_url = article['url'].split('?')[0].split('#')[0]
                if not await is_posted(clean_url):
                    kurdish_text = await process_smart_news(article['title'])
                    if kurdish_text:
                        await mark_posted(clean_url)
                        text = await format_post(kurdish_text, clean_url)
                        
                        try:
                            if article.get('image_url'):
                                await bot.send_photo(chat_id=Config.CHANNEL_ID, photo=article['image_url'], caption=text, parse_mode="HTML")
                            else:
                                await bot.send_message(chat_id=Config.CHANNEL_ID, text=text, parse_mode="HTML", disable_web_page_preview=True)
                        except Exception as e:
                            logger.error(f"Telegram send error: {e}")

                        post_to_facebook(text, image_url=article.get('image_url'), link_url=clean_url)

                        article['title_ku'] = kurdish_text
                        await save_news(article)
                        await asyncio.sleep(Config.POST_DELAY_SECONDS)
                    else:
                        await mark_posted(clean_url)

            await asyncio.sleep(Config.CHECK_INTERVAL_SECONDS)

        except Exception as e:
            logger.error(f"Main loop error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(run_bot())
