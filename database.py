import aiosqlite
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "bot.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                subscribed_at TEXT,
                expires_at TEXT,
                active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                prize TEXT NOT NULL,
                draw_date TEXT NOT NULL,
                description TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS winners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giveaway_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                won_at TEXT,
                FOREIGN KEY (giveaway_id) REFERENCES giveaways(id)
            )
        """)
        await db.commit()

async def add_subscriber(user_id: int, username: str, full_name: str, expires_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO subscribers
            (user_id, username, full_name, subscribed_at, expires_at, active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (user_id, username, full_name, datetime.now().isoformat(), expires_at))
        await db.commit()

async def get_active_subscribers():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT user_id, username, full_name, expires_at
            FROM subscribers WHERE active = 1
        """) as cursor:
            return await cursor.fetchall()

async def get_subscriber(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT user_id, expires_at, active FROM subscribers WHERE user_id = ?
        """, (user_id,)) as cursor:
            return await cursor.fetchone()

async def deactivate_subscriber(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE subscribers SET active = 0 WHERE user_id = ?
        """, (user_id,))
        await db.commit()

async def get_expiring_soon():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT user_id, username, expires_at
            FROM subscribers
            WHERE active = 1
            AND DATE(expires_at) = DATE('now', '+3 days')
        """) as cursor:
            return await cursor.fetchall()

async def get_expired():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT user_id FROM subscribers
            WHERE active = 1
            AND DATE(expires_at) < DATE('now')
        """) as cursor:
            return await cursor.fetchall()

async def add_giveaway(prize: str, draw_date: str, description: str = "", title: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE giveaways SET active = 0
        """)
        cursor = await db.execute("""
            INSERT INTO giveaways (title, prize, draw_date, description, active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (title or prize, prize, draw_date, description, datetime.now().isoformat()))
        await db.commit()
        return cursor.lastrowid

async def get_active_giveaway():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT id, title, prize, draw_date, description
            FROM giveaways WHERE active = 1
            ORDER BY id DESC LIMIT 1
        """) as cursor:
            return await cursor.fetchone()

async def add_winner(giveaway_id: int, user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO winners (giveaway_id, user_id, username, full_name, won_at)
            VALUES (?, ?, ?, ?, ?)
        """, (giveaway_id, user_id, username, full_name, datetime.now().isoformat()))
        await db.execute("UPDATE giveaways SET active = 0 WHERE id = ?", (giveaway_id,))
        await db.commit()

async def get_winners():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT w.full_name, w.username, w.won_at, g.prize
            FROM winners w
            JOIN giveaways g ON w.giveaway_id = g.id
            ORDER BY w.won_at DESC
            LIMIT 10
        """) as cursor:
            return await cursor.fetchall()
