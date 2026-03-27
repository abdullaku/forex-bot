import os
import logging
import aiohttp

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ SUPABASE_URL or SUPABASE_KEY is not set in environment variables")


async def setup_db():
    logger.info("✅ Database ready!")


async def is_posted(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{SUPABASE_URL}/rest/v1/posted_urls?url=eq.{url}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json"
                }
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"is_posted Supabase error {resp.status}: {text}")
                    return False

                data = await resp.json()
                return len(data) > 0

    except Exception as e:
        logger.error(f"is_posted error: {e}")
        return False


async def mark_posted(url):
    try:
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
                if resp.status not in (200, 201):
                    text = await resp.text()
                    logger.error(f"mark_posted Supabase error {resp.status}: {text}")

    except Exception as e:
        logger.error(f"mark_posted error: {e}")
