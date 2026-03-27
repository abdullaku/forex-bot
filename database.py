import os
import logging
import aiohttp

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


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
        await session.post(
            f"{SUPABASE_URL}/rest/v1/posted_urls",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            },
            json={"url": url}
        )


async def setup_db():
    logger.info("Database ready ✅")
