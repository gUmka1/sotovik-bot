import asyncio
import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
)

from database import (
    init_db, add_subscriber, get_active_subscribers,
    deactivate_subscriber, get_expiring_soon, get_expired,
    add_giveaway, get_active_giveaway, add_winner
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN    = os.getenv("BOT_TOKEN")
CHANNEL_ID   = int(os.getenv("CHANNEL_ID"))
ADMIN_ID     = int(os.getenv("ADMIN_ID"))
YUKASSA_TOKEN = os.getenv("YUKASSA_TOKEN")
WEBAPP_URL   = os.getenv("WEBAPP_URL")
PRICE = 30000

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()
router = Router()


def main_kb():
    buttons = [[InlineKeyboardButton(text="💳 Оформить подписку — 300 ₽/мес", callback_data="pay")]]
    if WEBAPP_URL:
        buttons.insert(0, [InlineKeyboardButton(text="🎰 Открыть Сотовик Клуб", web_app=WebAppInfo(url=WEBAPP_URL))])
    buttons.append([InlineKeyboardButton(text="❓ Как устроен розыгрыш?", callback_data="faq")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("start"))
async def cmd_start(message: Message):
    name = message.from_user.first_name
    await message.answer(
        f"👋 Привет, {name}!\n\n"
        "🏆 <b>Сотовик Клуб</b> — закрытый клуб с ежемесячными розыгрышами техники.\n\n"
        "Что входит в подписку:\n"
        "• Доступ в закрытый Telegram-канал\n"
        "• Участие в розыгрыше каждый месяц\n"
        "• Прямой эфир с объявлением победителя\n\n"
        "💰 <b>300 ₽ / месяц</b>\n\n"
        "Нажми чтобы оформить 👇",
        parse_mode="HTML",
        reply_markup=main_kb()
    )


@router.callback_query(F.data == "faq")
async def process_faq(callback):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="pay")]
    ])
    await callback.message.answer(
        "❓ <b>Как устроен розыгрыш?</b>\n\n"
        "1. Ты оформляешь подписку и попадаешь в закрытый канал\n"
        "2. В конце каждого месяца проводим прямой эфир\n"
        "3. Победитель выбирается случайно среди всех активных подписчиков\n"
        "4. Приз — техника (смартфон, наушники, гаджеты)\n\n"
        "📌 Чем дольше ты в клубе — тем больше розыгрышей пропустил бы без подписки 😉",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "pay")
async def process_pay(callback):
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Подписка Сотовик Клуб",
        description="Закрытый канал + розыгрыш техники каждый месяц в прямом эфире",
        payload="subscription_1month",
        provider_token=YUKASSA_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label="Подписка на 1 месяц", amount=PRICE)],
        start_parameter="subscription"
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message):
    user = message.from_user
    expires_at = (datetime.now() + timedelta(days=30)).isoformat()

    await add_subscriber(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name,
        expires_at=expires_at
    )

    invite = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        member_limit=1,
        expire_date=int((datetime.now() + timedelta(hours=24)).timestamp())
    )

    expires_str = (datetime.now() + timedelta(days=30)).strftime('%d.%m.%Y')
    await message.answer(
        f"🎉 <b>Добро пожаловать в Сотовик Клуб!</b>\n\n"
        f"Оплата прошла успешно.\n\n"
        f"👇 Ссылка для входа в канал (действует 24 часа):\n"
        f"{invite.invite_link}\n\n"
        f"📅 Подписка активна до: <b>{expires_str}</b>\n\n"
        f"Удачи в розыгрыше! 🏆",
        parse_mode="HTML"
    )

    subscribers = await get_active_subscribers()
    await bot.send_message(
        ADMIN_ID,
        f"💰 <b>Новый подписчик!</b>\n\n"
        f"👤 {user.full_name}\n"
        f"🔗 @{user.username or 'без username'}\n"
        f"🆔 {user.id}\n"
        f"📅 До: {expires_str}\n\n"
        f"👥 Всего активных: {len(subscribers)}",
        parse_mode="HTML"
    )


@router.message(Command("subscribers"))
async def cmd_subscribers(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    subscribers = await get_active_subscribers()
    if not subscribers:
        await message.answer("Активных подписчиков нет.")
        return
    text = f"👥 <b>Активных подписчиков: {len(subscribers)}</b>\n\n"
    for _, username, full_name, expires_at in subscribers:
        expires = datetime.fromisoformat(expires_at).strftime('%d.%m.%Y')
        uname = f"@{username}" if username else "—"
        text += f"• {full_name} ({uname}) · до {expires}\n"
    await message.answer(text, parse_mode="HTML")


@router.message(Command("kick"))
async def cmd_kick(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /kick USER_ID")
        return
    user_id = int(args[1])
    await bot.ban_chat_member(CHANNEL_ID, user_id)
    await bot.unban_chat_member(CHANNEL_ID, user_id)
    await deactivate_subscriber(user_id)
    await message.answer(f"✅ Пользователь <code>{user_id}</code> удалён из канала.", parse_mode="HTML")


@router.message(Command("add_giveaway"))
async def cmd_add_giveaway(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    # Format: /add_giveaway iPhone 16 Pro | 2026-06-30 | Главный приз месяца
    parts = message.text.removeprefix("/add_giveaway").strip().split("|")
    if len(parts) < 2:
        await message.answer(
            "Использование:\n"
            "<code>/add_giveaway ПРИЗ | ДАТА | ОПИСАНИЕ</code>\n\n"
            "Пример:\n"
            "<code>/add_giveaway iPhone 16 Pro | 2026-06-30 | Смартфон Apple 256Gb</code>",
            parse_mode="HTML"
        )
        return
    prize       = parts[0].strip()
    draw_date   = parts[1].strip()
    description = parts[2].strip() if len(parts) > 2 else ""
    giveaway_id = await add_giveaway(prize=prize, draw_date=draw_date, description=description)
    await message.answer(
        f"✅ Розыгрыш <b>#{giveaway_id}</b> создан!\n\n"
        f"🎁 Приз: {prize}\n"
        f"📅 Дата: {draw_date}\n"
        f"📝 {description or '—'}",
        parse_mode="HTML"
    )


@router.message(Command("set_winner"))
async def cmd_set_winner(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /set_winner USER_ID")
        return
    user_id = int(args[1])
    giveaway = await get_active_giveaway()
    if not giveaway:
        await message.answer("Нет активного розыгрыша. Создай через /add_giveaway")
        return
    try:
        chat_member = await bot.get_chat_member(CHANNEL_ID, user_id)
        full_name = chat_member.user.full_name
        username  = chat_member.user.username or ""
    except Exception:
        full_name = str(user_id)
        username  = ""
    await add_winner(
        giveaway_id=giveaway[0],
        user_id=user_id,
        username=username,
        full_name=full_name
    )
    await message.answer(
        f"🏆 <b>Победитель записан!</b>\n\n"
        f"👤 {full_name} (@{username or '—'})\n"
        f"🎁 Приз: {giveaway[2]}",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(
            user_id,
            f"🎉 <b>Поздравляем! Ты победил в розыгрыше!</b>\n\n"
            f"🎁 Приз: <b>{giveaway[2]}</b>\n\n"
            f"Свяжись с организатором для получения приза.",
            parse_mode="HTML"
        )
    except Exception:
        pass


async def scheduler():
    while True:
        await asyncio.sleep(43200)

        expiring = await get_expiring_soon()
        for user_id, _, expires_at in expiring:
            expires = datetime.fromisoformat(expires_at).strftime('%d.%m.%Y')
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Продлить подписку", callback_data="pay")]
            ])
            try:
                await bot.send_message(
                    user_id,
                    f"⏰ <b>Подписка истекает {expires}</b>\n\n"
                    f"Не забудь продлить — иначе потеряешь доступ к каналу и пропустишь розыгрыш в этом месяце!",
                    parse_mode="HTML",
                    reply_markup=kb
                )
            except Exception:
                pass

        expired = await get_expired()
        for (user_id,) in expired:
            try:
                await bot.ban_chat_member(CHANNEL_ID, user_id)
                await bot.unban_chat_member(CHANNEL_ID, user_id)
                await deactivate_subscriber(user_id)
                await bot.send_message(
                    user_id,
                    "😔 <b>Подписка закончилась</b>\n\n"
                    "Ты был удалён из закрытого канала.\n"
                    "Оформи снова — и сразу вернёшься + попадёшь в ближайший розыгрыш! 🏆",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Оформить снова — 300 ₽/мес", callback_data="pay")]
                    ])
                )
            except Exception:
                pass


dp.include_router(router)


async def main():
    await init_db()
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
