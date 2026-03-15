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

async def prefetch_urls(scraper):
    logger.info("⏳ پیشەوەنین هەواڵە کۆنەکان...")
    articles = await scraper.fetch_all()
    urls = {a['url'].split('?')[0] for a in articles}
    logger.info(f"✅ {len(urls)} هەواڵی کۆن تۆمار کرا")
    return urls

async def run_bot():
    bot = Bot(token=Config.BOT_TOKEN)
    scraper = NewsScraper()
    posted_urls = await prefetch_urls(scraper)
    logger.info("🤖 Forex Bot started!")
    await bot.send_message(
        chat_id=Config.CHANNEL_ID,
        text="🤖 بۆتی هەواڵی فۆرێکس چالاک بوو!\nهەموو ١٥ خولەکێک هەواڵی نوێ بە کوردی دەنێرم 📊"
    )
    while True:
        try:
            articles = await scraper.fetch_all()
            seen_urls = set()
            seen_titles = set()
            new_articles = []
            for a in articles:
                clean = a['url'].split('?')[0]
                title_short = a['title'].strip().lower()[:50]
                if clean not in posted_urls and clean not in seen_urls and title_short not in seen_titles:
                    seen_urls.add(clean)
                    seen_titles.add(title_short)
                    a['url'] = clean
                    new_articles.append(a)
            logger.info(f"هەواڵی نوێ: {len(new_articles)}")
            for article in new_articles:
                posted_urls.add(article['url'])
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
