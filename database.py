import aiosqlite
from pathlib import Path

DB_PATH = Path("bot.db")


class Database:
    def __init__(self, path=DB_PATH):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            # Пользователи
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_promo TIMESTAMP
                )
            """)

            # История выданных промокодов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promo_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER,
                    promo_code TEXT,
                    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.commit()

    async def add_user(self, telegram_id, username, first_name):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (telegram_id, username, first_name)
                VALUES (?, ?, ?)
            """, (telegram_id, username, first_name))
            await db.commit()

    async def update_last_promo(self, telegram_id):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                UPDATE users
                SET last_promo = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (telegram_id,))
            await db.commit()

    async def get_last_promo(self, telegram_id):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("""
                SELECT last_promo FROM users
                WHERE telegram_id = ?
            """, (telegram_id,))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def add_promo_history(self, telegram_id, code):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT INTO promo_history (telegram_id, promo_code)
                VALUES (?, ?)
            """, (telegram_id, code))
            await db.commit()

    async def get_user_history(self, telegram_id):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("""
                SELECT promo_code, issued_at
                FROM promo_history
                WHERE telegram_id = ?
                ORDER BY issued_at DESC
            """, (telegram_id,))
            return await cursor.fetchall()

    async def count_users(self):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            return (await cursor.fetchone())[0]

    async def count_total_promos(self):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM promo_history")
            return (await cursor.fetchone())[0]
