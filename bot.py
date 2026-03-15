import asyncio
import logging
from telegram import Bot
from sources import NewsScraper
from translator import translate_to_kurdish
from config import Config
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def format_post(article):
    emojis = {"economic_news":"📊","technical_analysis":"📈","forex_signal":"🎯","live_rates":"💹"}
    emoji = emojis.get(article.get("category",""),"📰")
    post = f"{emoji} {article['title_ku']}\n\n{article['summary_ku']}\n\n"
    if article.get("pairs"):
        post += f"💱 جووتەکان: {', '.join(article['pairs'])}\n"
    if article.get("signal"):
        s = article["signal"]
        d = "🟢" if s.get("direction")=="BUY" else "🔴"
        post += f"\n{d} سگنال: {s.get('direction','')}\n"
        if s.get("entry"): post += f"📍 چوونەژوورەوە: {s['entry']}\n"
        if s.get("tp"): post += f"✅ ئامانج: {s['tp']}\n"
        if s.get("sl"): post += f"❌ وەقفکردن: {s['sl']}\n"
    post += f"\n🔗 سەرچاوە: {article['source']} - {article['url']}"
    post += f"\n🕐 {datetime.now().strftime('%H:%M | %d/%m/%Y')}"
    return post

async def prefetch_urls(scraper):
    """کۆتا هەواڵەکان بیر بکەرەوە بەبێ ئەوەی بینێرێت"""
    logger.info("⏳ پیشەوەنین هەواڵە کۆنەکان...")
    articles = await scraper.fetch_all()
    urls = {a['url'] for a in articles}
    logger.info(f"✅ {len(urls)} هەواڵی کۆن تۆمار کرا")
    return urls

async def run_bot():
    bot = Bot(token=Config.BOT_TOKEN)
    scraper = NewsScraper()
    
    # هەواڵە کۆنەکان بیر بکەرەوە بەبێ ناردن
    posted_urls = await prefetch_urls(scraper)
    
    logger.info("🤖 Forex Bot started!")
    await bot.send_message(chat_id=Config.CHANNEL_ID, text="🤖 بۆتی هەواڵی فۆرێکس چالاک بوو!\n\nهەموو کاتێک هەواڵ و ئەنالیزی نوێی فۆرێکس بۆتان دەنێرم 📊")
    
    while True:
        try:
            articles = await scraper.fetch_all()
            new_articles = [a for a in articles if a['url'] not in posted_urls]
            logger.info(f"هەواڵی نوێ: {len(new_articles)}")
            for article in new_articles:
                article = await translate_to_kurdish(article)
                await asyncio.sleep(Config.TRANSLATE_DELAY_SECONDS)
                text = await format_post(article)
                await bot.send_message(chat_id=Config.CHANNEL_ID, text=text)
                posted_urls.add(article['url'])
                await asyncio.sleep(Config.POST_DELAY_SECONDS)
            await asyncio.sleep(Config.CHECK_INTERVAL_SECONDS)
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(run_bot())
