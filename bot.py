import asyncio
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Bot
from sources import NewsScraper
from translator import translate_to_kurdish
from config import Config
from database import setup_db, is_posted, mark_posted
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
    def log_message(self, format, *args):
        pass

def run_server():
    HTTPServer(('0.0.0.0', int(os.getenv('PORT', 4000))), Handler).serve_forever()

async def format_post(article):
    emojis = {"economic_news":"📊","technical_analysis":"📈","forex_signal":"🎯","live_rates":"💹"}
    category_names = {"economic_news":"هەواڵی ئابووری","technical_analysis":"ئەنالیزی تەکنیکی","forex_signal":"سگنالی فۆرێکس","live_rates":"نرخی زیندوو"}
    emoji = emojis.get(article.get("category",""),"📰")
    category_name = category_names.get(article.get("category",""),"هەواڵ")
    post = f"{emoji} {article['title_ku']}\n\n"
    post += f"{article['summary_ku']}\n\n"
    if article.get("pairs"):
        post += f"💱 {', '.join(article['pairs'])}\n\n"
    post += f"📌 {article['source']} | {category_name}\n"
    post += f"🔗 <a href='{article['url']}'>بینە هەواڵەکە</a>\n"
    post += f"🕐 {datetime.now().strftime('%H:%M | %d/%m/%Y')}"
    return post

def is_kurdish(text):
    kurdish_chars = set('ابتثجحخدذرزسشصضطظعغفقكلمنهوي\u06a9\u06af\u06c1\u06be\u0698\u0686\u06cc\u06d5\u06c6\u06c7\u06c8\u06cb\u06cf\u06b5\u06b1\u0695\u067e\u062c\u06a4')
    count = sum(1 for c in text if c in kurdish_chars)
    return count > len(text) * 0.2

async def run_bot():
    threading.Thread(target=run_server, daemon=True).start()
    bot = Bot(token=Config.BOT_TOKEN)
    scraper = NewsScraper()
    await setup_db()
    logger.info("🤖 Forex Bot started!")
    await bot.send_message(
        chat_id=Config.CHANNEL_ID,
        text="🤖 بۆتی هەواڵی فۆرێکس چالاک بوو!\nهەموو ١٥ خولەکێک هەواڵی نوێ بە کوردی دەنێرم 📊"
    )
    while True:
        try:
            articles = await scraper.fetch_all()
            new_articles = []
            for a in articles:
                clean = a['url'].split('?')[0]
                if not await is_posted(clean):
                    a['url'] = clean
                    new_articles.append(a)
            logger.info(f"هەواڵی نوێ: {len(new_articles)}")
            for article in new_articles:
                await mark_posted(article['url'])
                article = await translate_to_kurdish(article)
                await asyncio.sleep(Config.TRANSLATE_DELAY_SECONDS)
                if article.get('title_ku') and is_kurdish(article['title_ku']):
                    text = await format_post(article)
                    await bot.send_message(chat_id=Config.CHANNEL_ID, text=text, parse_mode="HTML")
                    logger.info(f"✅ Posted: {article['title_ku'][:40]}")
                    await asyncio.sleep(Config.POST_DELAY_SECONDS)
                else:
                    logger.warning(f"⚠️ Skipped: {article.get('title_ku','')[:40]}")
            await asyncio.sleep(Config.CHECK_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(run_bot())
