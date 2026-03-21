import asyncio
import logging
import requests
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
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

FB_BOT_TOKEN = "8541993321:AAHAZk0-599M17p-ejvyUizjpd0NVOhho7g"
FB_CHANNEL_ID = -1003829360084
FACEBOOK_PAGE_TOKEN = "EAAUuD0sVsdcBRBLiIFF8Pts6QoDsvvBJqVQxknagY6lKuqvD1AOzIypDJzrkBG5SPD64VD3TkMbyr78BLzhKCfsS0vzsrCQqysBpKQnk4QjVf4EHtoAEHVboQlwC7ixDvQjFWZBk2ZC5dJfuVopkD1Mr7JEDWJ0Oq7VM7Q3EL4xbS3pjRB76VFNTZALRQRz4UfRggxYsDR0uSsWbZBAFpW88JEZBBbTuO8eGejI3r1UR1"
FACEBOOK_PAGE_ID = "994664793738553"

def post_to_facebook(text, image_url=None, link_url=None):
    import re
    # پێش سڕینەوەی HTML — لینک لە href دەربهێنە
    if not link_url:
        href_match = re.search(r"href=['\"]([^'\"]+)['\"]", text)
        if href_match:
            link_url = href_match.group(1)
    clean_text = re.sub(r'<[^>]+>', '', text)
    if not link_url:
        urls = re.findall(r'https?://\S+', clean_text)
        if urls:
            link_url = urls[0]
    try:
        if image_url:
            url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/photos"
            data = {"url": image_url, "caption": clean_text, "access_token": FACEBOOK_PAGE_TOKEN}
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
        logger.error(f"❌ هەڵە: {e}")

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.channel_post
    if not message or message.chat.id != FB_CHANNEL_ID:
        return
    text = message.text or message.caption or ""
    image_url = None
    link_url = None
    if message.photo:
        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_url = file.file_path
    if message.entities:
        for entity in message.entities:
            if entity.type == "url":
                link_url = text[entity.offset:entity.offset + entity.length]
                break
            elif entity.type == "text_link":
                link_url = entity.url
                break
    if message.caption_entities:
        for entity in message.caption_entities:
            if entity.type == "url":
                link_url = text[entity.offset:entity.offset + entity.length]
                break
            elif entity.type == "text_link":
                link_url = entity.url
                break
    if text or image_url:
        logger.info(f"📨 پۆستی نوێ بۆ فەیسبووک: {text[:50]}")
        post_to_facebook(text, image_url, link_url)

async def run_fb_sync_async():
    app = Application.builder().token(FB_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handle_channel_post))
    logger.info("🔄 FB Sync Bot دەستی کرد...")
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

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
                    if act_val > fore_val:
                        result_emoji = "✅ زیاتر — ئەرێنی"
                    elif act_val < fore_val:
                        result_emoji = "❌ کەمتر — نەرێنی"
                    else:
                        result_emoji = "➡️ وەک پێشبینی"
                except:
                    result_emoji = "📊"
                msg = f"🔴 <b>ئەنجامی هەواڵی گرنگ</b>\n\n"
                msg += f"🏛 {title} | {currency}\n\n"
                msg += f"▪️ پێشوو: {previous}\n"
                msg += f"▪️ پێشبینی: {forecast}\n"
                msg += f"▫️ ئەنجام: <b>{actual}</b>\n\n"
                msg += f"{result_emoji}\n\n"
                msg += f"🕐 {now.strftime('%H:%M | %d/%m/%Y')}"
                await bot.send_message(chat_id=Config.CHANNEL_ID, text=msg, parse_mode="HTML")
            elif not actual and 45 <= diff_minutes <= 75 and event_id not in alerted_events:
                alerted_events.add(event_id)
                msg = f"⚠️ <b>ئاگادارکردنەوە — دوای ١ کاتژمێر</b>\n\n"
                msg += f"🔴 {title} | {currency}\n\n"
                msg += f"▪️ پێشوو: {previous}\n"
                msg += f"▪️ پێشبینی: {forecast}\n\n"
                msg += f"⏰ کات: {event_dt_baghdad.strftime('%H:%M')}\n"
                msg += f"🕐 {now.strftime('%H:%M | %d/%m/%Y')}"
                await bot.send_message(chat_id=Config.CHANNEL_ID, text=msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Calendar alert error: {e}")

async def run_bot():
    bot = Bot(token=Config.BOT_TOKEN)
    scraper = NewsScraper()
    await setup_db()
    logger.info("🤖 Forex Bot started with Deep Analysis and Keep-Alive!")
    asyncio.create_task(run_fb_sync_async())
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
                    last_calendar_day = current_day
            await check_calendar_alerts(bot, alerted_events, posted_results)
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
