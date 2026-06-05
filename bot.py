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

BOT_TOKEN     = os.getenv("BOT_TOKEN")
CHANNEL_ID    = int(os.getenv("CHANNEL_ID"))
ADMIN_ID      = int(os.getenv("ADMIN_ID"))
YUKASSA_TOKEN = os.getenv("YUKASSA_TOKEN")
WEBAPP_URL    = os.getenv("WEBAPP_URL")
MANUAL_PHONE  = os.getenv("MANUAL_PHONE", "")
MANUAL_CARD   = os.getenv("MANUAL_CARD", "")
MANUAL_NAME   = os.getenv("MANUAL_NAME", "")
PRICE = 100000

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()
router = Router()


def main_kb():
    buttons = [
        [InlineKeyboardButton(text="💳 Оплатить картой — 1000 ₽/мес", callback_data="pay")],
        [InlineKeyboardButton(text="📱 Оплатить через СБП / перевод", callback_data="pay_manual")],
    ]
    if WEBAPP_URL:
        buttons.insert(0, [InlineKeyboardButton(text="🎰 Открыть Сотовик Клуб", web_app=WebAppInfo(url=WEBAPP_URL))])
    buttons.append([
        InlineKeyboardButton(text="❓ Как устроен розыгрыш?", callback_data="faq"),
        InlineKeyboardButton(text="📋 Условия", callback_data="conditions"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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
        "💰 <b>1000 ₽ / месяц</b>\n\n"
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
        "2. Получаешь доступ к оптовым закупочным ценам на ориг. технику Apple, Dyson, Sony и других брендов\n"
        "3. В конце каждого месяца — прямой эфир с розыгрышем\n"
        "4. Победитель выбирается случайно среди всех активных подписчиков\n"
        "5. Призы: iPhone 17 / 17 Pro / 17 Pro Max, MacBook, iMac, AirPods\n\n"
        "📌 Чем дольше ты в клубе — тем больше розыгрышей пропустил бы без подписки 😉",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "conditions")
async def process_conditions(callback):
    text = (
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="pay")]
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
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


@router.callback_query(F.data == "pay_manual")
async def process_pay_manual(callback):
    user = callback.from_user
    lines = []
    if MANUAL_PHONE:
        lines.append(f"📱 <b>Телефон (СБП):</b> <code>{MANUAL_PHONE}</code>")
    if MANUAL_CARD:
        lines.append(f"💳 <b>Номер карты:</b> <code>{MANUAL_CARD}</code>")
    if MANUAL_NAME:
        lines.append(f"👤 <b>Получатель:</b> {MANUAL_NAME}")
    if not lines:
        await callback.answer("Реквизиты ещё не настроены. Свяжитесь с администратором.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"user_paid_{user.id}")]
    ])
    await callback.message.answer(
        f"📱 <b>Оплата через СБП или перевод</b>\n\n"
        f"Переведите <b>1 000 ₽</b> по реквизитам:\n\n"
        + "\n".join(lines) +
        f"\n\n💬 В комментарии укажите: <code>Сотовик {user.id}</code>\n\n"
        f"После перевода нажмите кнопку — мы проверим и выдадим доступ в течение нескольких минут.",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_paid_"))
async def process_user_paid(callback):
    user = callback.from_user
    user_id = int(callback.data.split("_")[-1])
    if user.id != user_id:
        await callback.answer("Это не ваша кнопка.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{user_id}"),
        InlineKeyboardButton(text="❌ Отклонить",   callback_data=f"reject_{user_id}"),
    ]])
    await bot.send_message(
        ADMIN_ID,
        f"💰 <b>Заявка на оплату (СБП/перевод)</b>\n\n"
        f"👤 {user.full_name}\n"
        f"🔗 @{user.username or 'без username'}\n"
        f"🆔 <code>{user.id}</code>\n\n"
        f"Проверьте поступление 1 000 ₽ (комментарий: <code>Сотовик {user.id}</code>) и подтвердите.",
        parse_mode="HTML",
        reply_markup=kb
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(
        "⏳ <b>Заявка отправлена на проверку!</b>\n\n"
        "Обычно доступ открывается в течение нескольких минут.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("approve_"))
async def process_admin_approve(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    user_id = int(callback.data.split("_")[-1])
    expires_at  = (datetime.now() + timedelta(days=30)).isoformat()
    expires_str = (datetime.now() + timedelta(days=30)).strftime('%d.%m.%Y')
    try:
        chat = await bot.get_chat(user_id)
        full_name = chat.full_name or str(user_id)
        username  = chat.username or ""
    except Exception:
        full_name, username = str(user_id), ""
    await add_subscriber(user_id=user_id, username=username, full_name=full_name, expires_at=expires_at)
    invite = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        member_limit=1,
        expire_date=int((datetime.now() + timedelta(hours=24)).timestamp())
    )
    await bot.send_message(
        user_id,
        f"🎉 <b>Оплата подтверждена! Добро пожаловать в Сотовик Клуб!</b>\n\n"
        f"👇 Ссылка для входа (действует 24 часа):\n{invite.invite_link}\n\n"
        f"📅 Подписка активна до: <b>{expires_str}</b>\n\n"
        f"Удачи в розыгрыше! 🏆",
        parse_mode="HTML"
    )
    try:
        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ Подтверждено — доступ выдан до {expires_str}",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("Доступ выдан!")


@router.callback_query(F.data.startswith("reject_"))
async def process_admin_reject(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    user_id = int(callback.data.split("_")[-1])
    await bot.send_message(
        user_id,
        "❌ <b>Платёж не найден</b>\n\n"
        "Мы не обнаружили перевод на нашем счёте.\n"
        "Попробуй снова или напиши администратору.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Попробовать снова", callback_data="pay_manual")]
        ])
    )
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ Отклонено",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("Заявка отклонена.")


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
                        [InlineKeyboardButton(text="💳 Оформить снова — 1000 ₽/мес", callback_data="pay")]
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