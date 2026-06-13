import hashlib
import hmac
import json
import os
from urllib.parse import parse_qsl

import aiosqlite
from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
QR_PATH = os.path.join(os.path.dirname(__file__), "qrcod_foxI.png")

bot = Bot(token=BOT_TOKEN)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.getenv("DB_PATH", "bot.db")


def validate_init_data(init_data: str) -> dict | None:
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed, received_hash):
            return None
        user_json = parsed.get("user")
        return json.loads(user_json) if user_json else {}
    except Exception:
        return None


@app.get("/", response_class=HTMLResponse)
async def serve_app():
    with open("webapp/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT expires_at, active FROM subscribers WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        return {"subscribed": False}
    return {"subscribed": bool(row[1]), "expires_at": row[0]}


@app.get("/api/giveaway")
async def get_giveaway():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, title, prize, draw_date, description FROM giveaways WHERE active = 1 ORDER BY id DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
        async with db.execute("SELECT COUNT(*) FROM subscribers WHERE active = 1") as cursor:
            count = (await cursor.fetchone())[0]

    if not row:
        return {"giveaway": None, "participants": count}
    return {
        "giveaway": {
            "id": row[0], "title": row[1], "prize": row[2],
            "draw_date": row[3], "description": row[4]
        },
        "participants": count
    }


@app.get("/api/winners")
async def get_winners():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT w.full_name, w.username, w.won_at, g.prize
            FROM winners w JOIN giveaways g ON w.giveaway_id = g.id
            ORDER BY w.won_at DESC LIMIT 10
        """) as cursor:
            rows = await cursor.fetchall()
    return [
        {"full_name": r[0], "username": r[1], "won_at": r[2], "prize": r[3]}
        for r in rows
    ]


@app.post("/api/pay")
async def request_payment(request: Request):
    body = await request.json()
    user = validate_init_data(body.get("initData", ""))
    if not user:
        raise HTTPException(status_code=403, detail="Invalid initData")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_{user['id']}")]
    ])
    await bot.send_photo(
        chat_id=user["id"],
        photo=FSInputFile(QR_PATH),
        caption=(
            "💳 <b>Оплата подписки — 1000 ₽/мес</b>\n\n"
            "📱 <b>С телефона (СБП):</b>\n"
            "Открой банковское приложение → «Перевод по номеру телефона» → введи номер:\n"
            "<code>+7 911 909 2200</code>\n"
            "Сумма: <b>1000 ₽</b>\n\n"
            "🖥 <b>С компьютера:</b>\n"
            "Отсканируй QR-код камерой телефона\n\n"
            "После оплаты нажми <b>«✅ Я оплатил»</b> — проверим и откроем доступ в течение нескольких минут"
        ),
        parse_mode="HTML",
        reply_markup=kb
    )
    return {"ok": True}
