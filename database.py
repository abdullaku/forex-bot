import os
import logging
import aiohttp
import json

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://xekpxulamhgplnxfnczp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_3i3wA3W-__nQLysnBSB6sQ__Ye-Bn4P")

async def setup_db():
    logger.info("✅ Database ready!")

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
        async with session.post(
            f"{SUPABASE_URL}/rest/v1/news",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json={
                "title_ku": article.get("title_ku", ""),
                "summary_ku": article.get("summary_ku", ""),
                "source": article.get("source", ""),
                "url": article.get("url", ""),
                "pairs": ", ".join(article.get("pairs", []))
            }
        ) as resp:
            pass
