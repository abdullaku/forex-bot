import os
import logging
import aiohttp
import json

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://xekpxulamhgplnxfnczp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

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
