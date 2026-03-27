import os
import logging
import aiohttp

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


async def setup_db():
    logger.info("✅ Database ready!")


async def is_posted(url):
    try:
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
    except Exception as e:
        logger.error(f"is_posted error: {e}")
        return False


async def mark_posted(url):
    try:
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
    except Exception as e:
        logger.error(f"mark_posted error: {e}")
