import asyncpg
import os
import logging

logger = logging.getLogger(__name__)

async def get_db():
    return await asyncpg.connect(os.getenv("DATABASE_URL"))

async def setup_db():
    conn = await get_db()
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS posted_urls (
            url TEXT PRIMARY KEY,
            posted_at TIMESTAMP DEFAULT NOW()
        )
    """)
    await conn.close()
    logger.info("✅ Database ready!")

async def is_posted(url):
    conn = await get_db()
    result = await conn.fetchval("SELECT url FROM posted_urls WHERE url=$1", url)
    await conn.close()
    return result is not None

async def mark_posted(url):
    conn = await get_db()
    await conn.execute("INSERT INTO posted_urls(url) VALUES($1) ON CONFLICT DO NOTHING", url)
    await conn.close()
