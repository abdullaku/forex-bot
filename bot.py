import asyncio
import os
import logging
from telegram import Bot
from datetime import datetime
from flask import Flask
from threading import Thread
import aiohttp
import xml.etree.ElementTree as ET

# --- رێکخستنی سەرەکی ---
TOKEN = "8611761761:AAEU_XJjV8QQ3LPr2rWf6gDBNnH2TVbs3_E"
CHAT_ID = "-1003829360084"
# لێرە کلیلی Groq بەکاردێنین چونکە هی تۆ Groq بوو
GROQ_KEY = "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"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- فێڵێک بۆ ئەوەی Render نەخەوێت ---
app = Flask('')
@app.route('/')
def home(): return "بۆتەکە چالاکە!"
def run_flask(): app.run(host='0.0.0.0', port=8080)
Thread(target=run_flask).start()

# --- وەرگێڕانی خێرا بە Groq ---
async def translate_news(text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": f"Translate this finance news to Sorani Kurdish briefly: {text}"}]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                result = await resp.json()
                return result['choices'][0]['message']['content']
    except:
        return text

# --- کارکردنی بۆتەکە ---
async def run_bot():
    bot = Bot(token=TOKEN)
    posted_urls = set()
    logger.info("🚀 بۆتەکە بە خێرایی دەستی پێکرد...")

    while True:
        try:
            # پشکنینی RSS (تەنها یەک دانە بۆ خێرایی)
            async with aiohttp.ClientSession() as session:
                async with session.get("https://www.cnbc.com/id/10000664/device/rss/rss.html") as resp:
                    text = await resp.text()
                    root = ET.fromstring(text)
                    for item in root.findall('.//item')[:2]: # تەنها ٢ هەواڵی نوێ
                        link = item.findtext('link')
                        if link not in posted_urls:
                            title = item.findtext('title')
                            ku_title = await translate_news(title)
                            msg = f"<b>{ku_title}</b>\n\n🔗 {link}"
                            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")
                            posted_urls.add(link)
                            logger.info(f"✅ پۆست کرا: {title}")
            
            await asyncio.sleep(60) # هەر یەک خولەک جارێک بگەڕێ
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_bot())
    
