import os
import logging
import aiohttp
from urllib.parse import quote

logger = logging.getLogger(__name__)


class DatabaseConfig:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    @classmethod
    def validate(cls):
        if not cls.SUPABASE_URL or not cls.SUPABASE_KEY:
            raise ValueError("❌ SUPABASE_URL or SUPABASE_KEY is not set in environment variables")


DatabaseConfig.validate()


class DatabaseService:
    def __init__(self):
        self.base_url = DatabaseConfig.SUPABASE_URL
        self.api_key = DatabaseConfig.SUPABASE_KEY

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
        try:
            # ✅ URL کۆد دەکرێت پێش ناردن بۆ Supabase
            encoded_url = quote(url, safe="")
            request_url = f"{self.base_url}/rest/v1/posted_urls?url=eq.{encoded_url}"

            async with aiohttp.ClientSession() as session:
                async with session.get(request_url, headers=self.headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"is_posted Supabase error {resp.status}: {text}")
                        return False

                    data = await resp.json()
                    return len(data) > 0

        except Exception as e:
            logger.error(f"is_posted error: {e}")
            return False

    async def mark_posted(self, url):
        try:
            request_url = f"{self.base_url}/rest/v1/posted_urls"
            headers = {
                **self.headers,
                "Prefer": "return=minimal",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    request_url,
                    headers=headers,
                    json={"url": url}  # ✅ JSON body — کۆدکردن پێویست نیە
                ) as resp:
                    if resp.status not in (200, 201):
                        text = await resp.text()
                        logger.error(f"mark_posted Supabase error {resp.status}: {text}")

        except Exception as e:
            logger.error(f"mark_posted error: {e}")


_db = DatabaseService()


async def setup_db():
    await _db.setup()


async def is_posted(url):
    return await _db.is_posted(url)


async def mark_posted(url):
    await _db.mark_posted(url)
