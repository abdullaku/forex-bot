import os
import logging
import psycopg2

logger = logging.getLogger(__name__)

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

async def setup_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posted_urls (
            url TEXT PRIMARY KEY,
            posted_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    conn.close()
    logger.info("✅ Database ready!")

async def is_posted(url):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT url FROM posted_urls WHERE url=%s", (url,))
    result = cur.fetchone()
    conn.close()
    return result is not None

async def mark_posted(url):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO posted_urls(url) VALUES(%s) ON CONFLICT DO NOTHING", (url,))
    conn.commit()
    conn.close()
