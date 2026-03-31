import os
import logging
import asyncio
import urllib.parse
import aiohttp

logger = logging.getLogger(__name__)


class DatabaseConfig:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    @classmethod
    def validate(cls):
        if not cls.SUPABASE_URL or not cls.SUPABASE_KEY:
            raise ValueError("❌ SUPABASE_URL or SUPABASE_KEY is not set")


DatabaseConfig.validate()


class DatabaseService:
    def __init__(self):
        self.base_url = DatabaseConfig.SUPABASE_URL
        self.api_key = DatabaseConfig.SUPABASE_KEY
        self.timeout = aiohttp.ClientTimeout(total=10)

    @property
    def headers(self):
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def setup(self):
        logger.info("✅ Database ready!")

    async def is_posted(self, url):
        encoded_url = urllib.parse.quote(url, safe="")
        request_url = f"{self.base_url}/rest/v1/posted_urls?url=eq.{encoded_url}"

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.get(request_url, headers=self.headers) as resp:

                        if resp.status == 200:
                            data = await resp.json()
                            return len(data) > 0

                        if resp.status in (502, 503, 504):
                            logger.warning(f"⚠️ Supabase temporary error {resp.status} (try {attempt+1})")
                            await asyncio.sleep(2)
                            continue

                        text = await resp.text()
                        logger.error(f"is_posted error {resp.status}: {text}")
                        return False

            except Exception as e:
                logger.error(f"is_posted exception (try {attempt+1}): {e}")
                await asyncio.sleep(2)

        return False

    async def mark_posted(self, url):
        request_url = f"{self.base_url}/rest/v1/posted_urls"

        headers = {
            **self.headers,
            "Prefer": "return=minimal",
        }

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(
                        request_url,
                        headers=headers,
                        json={"url": url}
                    ) as resp:

                        if resp.status in (200, 201):
                            return True

                        # ✅ duplicate = normal
                        if resp.status == 409:
                            logger.info(f"ℹ️ Already exists: {url}")
                            return True

                        if resp.status in (502, 503, 504):
                            logger.warning(f"⚠️ Supabase temporary error {resp.status} (try {attempt+1})")
                            await asyncio.sleep(2)
                            continue

                        text = await resp.text()
                        logger.error(f"mark_posted error {resp.status}: {text}")
                        return False

            except Exception as e:
                logger.error(f"mark_posted exception (try {attempt+1}): {e}")
                await asyncio.sleep(2)

        return False


_db = DatabaseService()


async def setup_db():
    await _db.setup()


async def is_posted(url):
    return await _db.is_posted(url)


async def mark_posted(url):
    return await _db.mark_posted(url)
