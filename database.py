import aiosqlite
from pathlib import Path

DB_PATH = Path("bot.db")


class Database:
    def __init__(self, path=DB_PATH):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def add_user(self, telegram_id: int, username: str, first_name: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (telegram_id, username, first_name)
                VALUES (?, ?, ?)
            """, (telegram_id, username, first_name))
            await db.commit()

    async def get_all_users(self):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT telegram_id FROM users")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def count_users(self):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            count = await cursor.fetchone()
            return count[0]
