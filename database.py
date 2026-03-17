import os
import logging
import aiohttp
import json

logger = logging.getLogger(__name__)

# ئەمانە وەک خۆی لێ بگەڕێ یان لە ناو Render وەک Environment Variables دایبنێ
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://xekpxulamhgplnxfnczp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_3i3wA3W-__nQLysnBSB6sQ__Ye-Bn4P")

async def setup_db():
    logger.info("✅ Database ready with Image and Timestamp support!")

async def is_posted(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{SUPABASE_URL}/rest/v1/posted_urls?url=eq.{url}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            }
        ) as resp:
            data = await resp.json()
            return len(data) > 0

async def mark_posted(url):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SUPABASE_URL}/rest/v1/posted_urls",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json={"url": url}
        ) as resp:
            pass

async def save_news(article):
    async with aiohttp.ClientSession() as session:
        # ئامادەکردنی زانیارییەکان بۆ ناردن بۆ Supabase
        # لێرەدا image_url و published_at زیاد کراوە
        payload = {
            "title_ku": article.get("title_ku", ""),
            "summary_ku": article.get("summary_ku", ""),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "pairs": ", ".join(article.get("pairs", [])),
            "image_url": article.get("image_url", ""),
            "published_at": article.get("published_at", "")
        }
        
        async with session.post(
            f"{SUPABASE_URL}/rest/v1/news",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json=payload
        ) as resp:
            if resp.status != 201 and resp.status != 200:
                logger.error(f"❌ Error saving to Supabase: {resp.status}")
            else:
                logger.info("✅ News saved to Supabase successfully!")
                
