import asyncio
import logging
import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton
)

from database import (
    init_db, add_subscriber, get_active_subscribers,
    deactivate_subscriber, get_expiring_soon, get_expired,
    add_giveaway, get_active_giveaway, add_winner, get_subscriber
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN  = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMIN_IDS  = [int(x) for x in os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "")).replace(" ", "").split(",") if x]
WEBAPP_URL = os.getenv("WEBAPP_URL")

QR_PATH = os.path.join(os.path.dirname(__file__), "qrcod_foxI.png")

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()
router = Router()


async def notify_admins(text: str, **kwargs):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, **kwargs)
        except Exception:
            logging.exception("Failed to notify admin %s", admin_id)


async def _activate_user(user_id: int, full_name: str, username: str):
    expires_at = (datetime.now() + timedelta(days=30)).isoformat()
    await add_subscriber(user_id=user_id, username=username, full_name=full_name, expires_at=expires_at)
    expires_str = (datetime.now() + timedelta(days=30)).strftime('%d.%m.%Y')

    try:
        invite = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            expire_date=int((datetime.now() + timedelta(hours=24)).timestamp())
        )
        invite_link = invite.invite_link
    except Exception as e:
        logging.error("create_chat_invite_link failed for CHANNEL_ID=%s: %s", CHANNEL_ID, e)
        invite_link = None

    try:
        if invite_link:
            await bot.send_message(
                user_id,
                f"🎉 <b>Добро пожаловать в Сотовик Клуб!</b>\n\n"
                f"Оплата подтверждена.\n\n"
                f"👇 Ссылка для входа в канал (действует 24 часа):\n"
                f"{invite_link}\n\n"
                f"📅 Подписка активна до: <b>{expires_str}</b>\n\n"
                f"Удачи в розыгрыше! 🏆",
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                user_id,
                f"🎉 <b>Оплата подтверждена!</b>\n\n"
                f"📅 Подписка активна до: <b>{expires_str}</b>\n\n"
                f"Ссылку на канал администратор пришлёт вам в ближайшее время.",
                parse_mode="HTML"
            )
    except Exception as e:
        logging.error("Failed to message user %s after activation: %s", user_id, e)

    subscribers = await get_active_subscribers()
    link_status = invite_link or "⚠️ НЕ УДАЛОСЬ СОЗДАТЬ — отправь ссылку вручную!"
    await notify_admins(
        f"💰 <b>Новый подписчик!</b>\n\n"
        f"👤 {full_name}\n"
        f"🔗 @{username or 'без username'}\n"
        f"🆔 <code>{user_id}</code>\n"
        f"📅 До: {expires_str}\n"
        f"🔗 Инвайт: {link_status}\n\n"
        f"👥 Всего активных: {len(subscribers)}",
        parse_mode="HTML"
    )


def main_kb():
    buttons = [[InlineKeyboardButton(text="💳 Оформить подписку — 2400 ₽/мес", callback_data="pay")]]
    if WEBAPP_URL:
        buttons.insert(0, [InlineKeyboardButton(text="🎰 Открыть Сотовик Клуб", web_app=WebAppInfo(url=WEBAPP_URL))])
    buttons.append([
        InlineKeyboardButton(text="❓ Как устроен розыгрыш?", callback_data="faq"),
        InlineKeyboardButton(text="📋 Условия", callback_data="conditions"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


BTN_PAY    = "💳 Оформить подписку"
BTN_STATUS = "📊 Моя подписка"
BTN_FAQ    = "❓ Как устроен розыгрыш?"
BTN_TERMS  = "📋 Условия"
BTN_APP    = "🎰 Открыть Сотовик Клуб"


def main_reply_kb():
    rows = []
    if WEBAPP_URL:
        rows.append([KeyboardButton(text=BTN_APP, web_app=WebAppInfo(url=WEBAPP_URL))])
    rows.append([KeyboardButton(text=BTN_PAY), KeyboardButton(text=BTN_STATUS)])
    rows.append([KeyboardButton(text=BTN_FAQ), KeyboardButton(text=BTN_TERMS)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


@router.message(Command("start"))
async def cmd_start(message: Message):
    name = message.from_user.first_name
    await message.answer(
        f"👋 Привет, {name}!\n\n"
        "🏆 <b>Сотовик Клуб</b> — закрытый клуб с оптовыми ценами на технику и ежемесячными розыгрышами.\n\n"
        "Что входит в подписку:\n"
        "• 📦 Доступ к закупочным оптовым ценам на ориг. технику Apple, Dyson, Sony и других брендов\n"
        "• 🎰 Ежемесячный розыгрыш iPhone 17 / 17 Pro / 17 Pro Max, MacBook, iMac, AirPods\n"
        "• 📺 Прямой эфир с объявлением победителя\n\n"
        "💰 <b>2400 ₽ / месяц</b>\n\n"
        "Нажми чтобы оформить 👇",
        parse_mode="HTML",
        reply_markup=main_kb()
    )
    await message.answer("Меню всегда под рукой 👇", reply_markup=main_reply_kb())


@router.message(F.text == BTN_PAY)
async def menu_pay(message: Message):
    await process_pay_for(message.from_user.id)


@router.message(F.text == BTN_FAQ)
async def menu_faq(message: Message):
    await process_faq_for(message)


@router.message(F.text == BTN_TERMS)
async def menu_terms(message: Message):
    await process_conditions_for(message)


@router.message(F.text == BTN_STATUS)
async def menu_status(message: Message):
    sub = await get_subscriber(message.from_user.id)
    if not sub or not sub[2]:
        await message.answer(
            "❌ <b>Подписка не активна</b>\n\nОформи подписку — 2400 ₽/мес 👇",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="pay")]
            ])
        )
        return
    expires = datetime.fromisoformat(sub[1]).strftime('%d.%m.%Y')
    await message.answer(
        f"✅ <b>Подписка активна</b>\n\nДействует до: <b>{expires}</b>",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "faq")
async def process_faq(callback):
    await process_faq_for(callback.message)
    await callback.answer()


async def process_faq_for(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="pay")]
    ])
    await message.answer(
        "❓ <b>Как устроен розыгрыш?</b>\n\n"
        "1. Ты оформляешь подписку и попадаешь в закрытый канал\n"
        "2. Получаешь доступ к оптовым закупочным ценам на ориг. технику Apple, Dyson, Sony и других брендов\n"
        "3. В конце каждого месяца — прямой эфир с розыгрышем\n"
        "4. Победитель выбирается случайно среди всех активных подписчиков\n"
        "5. Призы: iPhone 17 / 17 Pro / 17 Pro Max, MacBook, iMac, AirPods\n\n"
        "📌 Чем дольше ты в клубе — тем больше розыгрышей пропустил бы без подписки 😉",
        parse_mode="HTML",
        reply_markup=kb
    )


CONDITIONS_TEXT = (
        "⚡️ <b>РОЗЫГРЫШ iPhone 17 PRO 256Gb ЗА ПОДПИСКУ</b>\n\n"
        "Хотите получить главный приз — новенький iPhone 17 PRO и ещё 9 оригинальных гаджетов для Apple iPhone?\n"
        "Вы уже с нами!?\n\n"
        "Федеральная Сеть Электроники <b>SOTOViK</b>, совместно с «DK Auto SPB» разыгрывают <b>iPhone 17 PRO 256 Gb</b> за подписку в закрытый канал 🔐\n\n"
        "<b>Что нужно сделать, чтобы участвовать?</b>\n\n"
        "1. Быть подписанным на официальный Telegram-канал SOTOViK (@sotovik_ru) и участвовать в нашем розыгрыше 30 Июня 2026г\n\n"
        "2. Подписаться на Telegram-канал нашего Автомобильного Партнёра «DK Auto SPb» (@dkautospb)\n\n"
        "3. Нажать кнопку «Принять участие» под постом | перейти в закрытый канал подписки, выполнить условия подписки\n\n"
        "4. Переслать розыгрыш трём своим друзьям (сохранить скрин пересылки) 📸\n\n"
        "<b>Условия получения призов:</b>\n"
        "— Победитель данного розыгрыша iPhone выбирает цвет на своё усмотрение.\n"
        "— Доставка осуществляется в любую точку РФ транспортной компанией СДЭК.\n"
        "— Чем больше друзей вы пригласите, тем выше ваши шансы на победу!\n\n"
        "📅 Итоги розыгрыша будут объявлены <b>30 июня 2026г. в 20:00</b> в нашем Telegram-канале!\n"
        "Победителей определит официальный бот-рандомайзер 🤖\n\n"
        "Не упустите шанс исполнить свою мечту — участвуйте прямо сейчас и пригласите друга!\n\n"
        "👥 Участников: 199\n"
        "🏆 Призовых мест: 10\n"
        "📅 Дата розыгрыша: 20:00, 30.06.2026 MSK (в процессе набора подписчиков)\n\n"
        "<b>Победителей/подписчиков закрытого канала SOTOViK ждут 10 призов:</b>\n\n"
        "1. 📱 iPhone 17 PRO 256 GB, гарантия от сервисного центра — 12 месяцев!\n"
        "2. 🎧 Наушники Apple AirPods 4 New\n"
        "3. 🔋 Портативная б/проводная зарядка VLP\n"
        "4. 🔋 MagSafe PowerBank VLP\n"
        "5. 👕🧢 Фирменный мерч SOTOViK\n"
        "6. 🧢👕 Фирменный мерч SOTOViK\n"
        "7. 👕🧢 Фирменный мерч SOTOViK\n"
        "8. ⚡️ Оригинальное сетевое зарядное устройство 20W Apple\n"
        "9. ⚡️ Оригинальное сетевое зарядное устройство 20W Apple\n"
        "10. ⚡️ Оригинальное сетевое зарядное устройство 20W Apple"
)


@router.callback_query(F.data == "conditions")
async def process_conditions(callback):
    await process_conditions_for(callback.message)
    await callback.answer()


async def process_conditions_for(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="pay")]
    ])
    await message.answer(CONDITIONS_TEXT, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "pay")
async def process_pay(callback):
    await process_pay_for(callback.from_user.id)
    await callback.answer()


async def process_pay_for(user_id: int):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_{user_id}")]
    ])
    await bot.send_photo(
        chat_id=user_id,
        photo=FSInputFile(QR_PATH),
        caption=(
            "💳 <b>Оплата подписки — 2400 ₽/мес</b>\n\n"
            "📱 <b>С телефона (СБП):</b>\n"
            "Открой банковское приложение → «Перевод по номеру телефона» → введи номер:\n"
            "<code>+7 911 909 2200</code>\n"
            "Сумма: <b>2400 ₽</b>\n\n"
            "🖥 <b>С компьютера:</b>\n"
            "Отсканируй QR-код камерой телефона\n\n"
            "После оплаты нажми <b>«✅ Я оплатил»</b> — проверим и откроем доступ в течение нескольких минут"
        ),
        parse_mode="HTML",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("paid_"))
async def process_paid(callback):
    user = callback.from_user
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{user.id}"),
        InlineKeyboardButton(text="❌ Отклонить",   callback_data=f"decline_{user.id}"),
    ]])
    await notify_admins(
        f"💰 <b>Запрос на подтверждение оплаты</b>\n\n"
        f"👤 {user.full_name}\n"
        f"🔗 @{user.username or 'без username'}\n"
        f"🆔 <code>{user.id}</code>",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer("Запрос отправлен! Подтвердим доступ в течение нескольких минут.", show_alert=True)


@router.callback_query(F.data.startswith("confirm_"))
async def process_confirm_payment(callback):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    user_id = int(callback.data.removeprefix("confirm_"))
    try:
        chat = await bot.get_chat(user_id)
        full_name = f"{chat.first_name or ''} {chat.last_name or ''}".strip() or str(user_id)
        username = chat.username or ""
    except Exception:
        full_name = str(user_id)
        username = ""
    try:
        await _activate_user(user_id, full_name, username)
    except Exception as e:
        logging.exception("Error activating user %s", user_id)
        await callback.answer(f"Ошибка: {e}", show_alert=True)
        return
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>Подтверждено! Доступ выдан.</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("Доступ выдан!", show_alert=True)


@router.callback_query(F.data.startswith("decline_"))
async def process_decline_payment(callback):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    user_id = int(callback.data.removeprefix("decline_"))
    try:
        await bot.send_message(
            user_id,
            "❌ <b>Оплата не подтверждена</b>\n\n"
            "Мы не нашли вашу оплату. Убедитесь что платёж прошёл и попробуйте снова.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Попробовать снова", callback_data="pay")]
            ])
        )
    except Exception:
        pass
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ <b>Отклонено.</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("Отклонено")


@router.message(Command("subscribers"))
async def cmd_subscribers(message: Message):
    if message.from_user.id not in ADMIN_IDS:
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
    if message.from_user.id not in ADMIN_IDS:
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


@router.message(Command("confirm"))
async def cmd_confirm(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /confirm USER_ID или /confirm @username")
        return
    arg = args[1]
    if arg.lstrip("-").isdigit():
        user_id = int(arg)
        try:
            chat = await bot.get_chat(user_id)
            full_name = f"{chat.first_name or ''} {chat.last_name or ''}".strip() or str(user_id)
            username = chat.username or ""
        except Exception:
            full_name = str(user_id)
            username = ""
    else:
        try:
            chat = await bot.get_chat(arg if arg.startswith("@") else f"@{arg}")
        except Exception:
            await message.answer(
                "Не удалось найти пользователя по username. "
                "Это работает только если пользователь уже хотя бы раз писал боту."
            )
            return
        user_id = chat.id
        full_name = f"{chat.first_name or ''} {chat.last_name or ''}".strip() or str(user_id)
        username = chat.username or ""
    await _activate_user(user_id, full_name, username)
    await message.answer(f"✅ Доступ выдан пользователю <code>{user_id}</code>", parse_mode="HTML")


@router.message(Command("add_giveaway"))
async def cmd_add_giveaway(message: Message):
    if message.from_user.id not in ADMIN_IDS:
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
    if message.from_user.id not in ADMIN_IDS:
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


def _draw_message(giveaway, subscribers):
    user_id, username, full_name, _ = random.choice(subscribers)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏆 Подтвердить победителя", callback_data=f"draw_ok_{giveaway[0]}_{user_id}"),
        InlineKeyboardButton(text="🔄 Другой",                 callback_data=f"draw_roll_{giveaway[0]}"),
    ]])
    text = (
        f"🎰 <b>Случайный победитель</b>\n\n"
        f"🎁 Приз: <b>{giveaway[2]}</b>\n"
        f"👥 Участников в пуле: <b>{len(subscribers)}</b>\n\n"
        f"🏆 <b>Победитель:</b>\n"
        f"👤 {full_name}\n"
        f"🔗 @{username or '—'}\n"
        f"🆔 <code>{user_id}</code>"
    )
    return text, kb


@router.message(Command("draw"))
async def cmd_draw(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    giveaway = await get_active_giveaway()
    if not giveaway:
        await message.answer("Нет активного розыгрыша. Создай через /add_giveaway")
        return
    subscribers = await get_active_subscribers()
    if not subscribers:
        await message.answer("Нет активных подписчиков для розыгрыша.")
        return
    text, kb = _draw_message(giveaway, subscribers)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("draw_roll_"))
async def process_draw_reroll(callback):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    giveaway = await get_active_giveaway()
    if not giveaway:
        await callback.answer("Розыгрыш уже завершён.", show_alert=True)
        return
    subscribers = await get_active_subscribers()
    if not subscribers:
        await callback.answer("Нет подписчиков.", show_alert=True)
        return
    text, kb = _draw_message(giveaway, subscribers)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("draw_ok_"))
async def process_draw_confirm(callback):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, _, giveaway_id, user_id = callback.data.split("_")
    giveaway_id, user_id = int(giveaway_id), int(user_id)
    giveaway = await get_active_giveaway()
    prize = giveaway[2] if giveaway else "Приз"
    subscribers = await get_active_subscribers()
    info = next((s for s in subscribers if s[0] == user_id), None)
    full_name = info[2] if info else str(user_id)
    username  = info[1] if info else ""
    await add_winner(giveaway_id=giveaway_id, user_id=user_id, username=username, full_name=full_name)
    try:
        await bot.send_message(
            user_id,
            f"🎉 <b>Поздравляем! Ты победил в розыгрыше!</b>\n\n"
            f"🎁 Приз: <b>{prize}</b>\n\n"
            f"Свяжись с организатором для получения приза.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>Победитель подтверждён и уведомлён!</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("Готово!")


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
                        [InlineKeyboardButton(text="💳 Оформить снова — 2400 ₽/мес", callback_data="pay")]
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