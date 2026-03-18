import asyncio
import os
import logging
from telegram import Bot
from datetime import datetime
from flask import Flask
from threading import Thread
import aiohttp
from bs4 import BeautifulSoup

# --- 1. ڕێکخستنی سەرەکی (Credentials) ---
TOKEN = "8611761761:AAEU_XJjV8QQ3LPr2rWf6gDBNnH2TVbs3_E"
CHAT_ID = "-1003829360084"
GROQ_KEY = "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"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. وێب سێرڤەر بۆ ئەوەی Render نەیخەوێنێت ---
app = Flask('')
@app.route('/')
def home(): return "بۆتەکە بە سەرکەوتوویی کار دەکات!"
def run_flask(): app.run(host='0.0.0.0', port=8080)
Thread(target=run_flask).start()

# --- 3. فرمانی وەرگێڕان بە بەکارهێنانی Groq ---
async def translate_news(text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": f"Translate this finance title to Sorani Kurdish in a professional news style: {text}"}]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data, timeout=10) as resp:
                result = await resp.json()
                return result['choices'][0]['message']['content'].strip()
    except Exception as e:
        logger.error(f"Translation Error: {e}")
        return text

# --- 4. فرمانی سەرەکی بۆتەکە ---
async def run_bot():
    bot = Bot(token=TOKEN)
    posted_urls = set()
    logger.info("🚀 بۆتەکە بە فەرمی دەستی پێکرد...")

    # --- پەیامی تاقیکاری (تەنها یەک جار کە بۆتەکە دادەگیرسێت دێت) ---
    try:
        await bot.send_message(chat_id=CHAT_ID, text="✅ سڵاو! من بە سەرکەوتوویی کار دەکەم و ئێستا چاوەڕێی هەواڵە نوێیەکانم.")
    except Exception as e:
        logger.error(f"Test Message Error: {e}")

    while True:
        try:
            # پشکنینی هەواڵەکان لە CNBC
            async with aiohttp.ClientSession() as session:
                async with session.get("https://www.cnbc.com/id/10000664/device/rss/rss.html", timeout=15) as resp:
                    content = await resp.text()
                    soup = BeautifulSoup(content, 'xml')
                    items = soup.find_all('item')
                    
                    for item in items[:5]: # پشکنینی 5 هەواڵی کۆتایی
                        link = item.link.text if item.link else ""
                        if link and link not in posted_urls:
                            title = item.title.text if item.title else ""
                            if title:
                                ku_title = await translate_news(title)
                                # ناردنی پۆستەکە بۆ تێلیگرام
                                msg = f"<b>📰 {ku_title}</b>\n\n🔗 {link}"
                                await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")
                                posted_urls.add(link)
                                logger.info(f"✅ پۆست کرا: {title}")
            
            # چاوەڕێ بکە بۆ 60 چرکە پێش پشکنینی دووبارە
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Bot Loop Error: {e}")
            await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(run_bot())
