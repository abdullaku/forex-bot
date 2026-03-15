import sqlite3

conn = sqlite3.connect("news.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS posted (
    url TEXT PRIMARY KEY
)
""")

conn.commit()


def is_posted(url):
    cursor.execute("SELECT url FROM posted WHERE url=?", (url,))
    return cursor.fetchone() is not None


def mark_posted(url):
    cursor.execute("INSERT OR IGNORE INTO posted VALUES (?)", (url,))
    conn.commit()
