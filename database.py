import sqlite3
import aiosqlite
from datetime import datetime

async def setup_db():
    async with aiosqlite.connect('news.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS news 
            (url TEXT PRIMARY KEY, title TEXT, timestamp TEXT)''')
        await db.commit()

async def is_posted(url):
    async with aiosqlite.connect('news.db') as db:
        async with db.execute("SELECT 1 FROM news WHERE url = ?", (url,)) as cursor:
            return await cursor.fetchone() is not None

async def mark_posted(url):
    async with aiosqlite.connect('news.db') as db:
        await db.execute("INSERT OR IGNORE INTO news (url) VALUES (?)", (url,))
        await db.commit()

async def save_news(article):
    async with aiosqlite.connect('news.db') as db:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await db.execute("UPDATE news SET title = ?, timestamp = ? WHERE url = ?", 
                         (article['title'], now, article['url']))
        await db.commit()

async def get_todays_news():
    today = datetime.now().strftime('%Y-%m-%d')
    async with aiosqlite.connect('news.db') as db:
        # ئەم بەشە زۆر گرنگە بۆ AI، چونکە هەموو هەواڵەکانی ئەمڕۆ کۆدەکاتەوە
        async with db.execute("SELECT title FROM news WHERE timestamp LIKE ?", (f"{today}%",)) as cursor:
            rows = await cursor.fetchall()
            return [{"title": row[0]} for row in rows if row[0]]
