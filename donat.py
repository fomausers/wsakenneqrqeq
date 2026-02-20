from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database

router = Router()

# Цены и награды (переведено в cron)
OFFERS = {
    "donat_25": {"stars": 1, "cron": 50000, "label": "⭐️ 25 Stars — 50 000 cron"},
    "donat_50": {"stars": 1, "cron": 104000, "label": "⭐️ 50 Stars — 104 000 cron"},
    "donat_100": {"stars": 1, "cron": 208000, "label": "⭐️ 100 Stars — 208 000 cron"},
}

@router.message(F.text.lower().in_(["донат", "/donate"]))
async def show_donate_menu(message: Message):
    if message.chat.type != "private":
        return await message.answer("❌ Команда доступна только в личных сообщениях с ботом.")

    builder = InlineKeyboardBuilder()
    for callback_data, info in OFFERS.items():
        builder.row(InlineKeyboardButton(text=info["label"], callback_data=callback_data))

    await message.answer(
        "<b>💎 Пополнение баланса через Telegram Stars</b>\n\n"
        "Выберите подходящий пакет:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("donat_"))
async def send_donation_invoice(callback: CallbackQuery, bot: Bot):
    offer_id = callback.data
    offer = OFFERS.get(offer_id)

    if not offer:
        return await callback.answer("Предложение не найдено.", show_alert=True)

    # В Telegram Stars валюта всегда "XTR"
    prices = [LabeledPrice(label="Cron Coins", amount=offer["stars"])]

    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Покупка cron",
        description=f"Пакет: {offer['cron']} cron",
        payload=f"{offer_id}_{callback.from_user.id}",  # Передаем ID оффера и ID юзера
        provider_token="",  # Для Telegram Stars токен всегда пустой
        currency="XTR",
        prices=prices,
        start_parameter="donate_cron"
    )
    await callback.answer()

# 1. Подтверждение платежа (Telegram требует этого перед снятием звезд)
@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

# 2. Обработка успешного платежа
@router.message(F.successful_payment)
async def on_successful_payment(message: Message):
    payment_info = message.successful_payment
    payload = payment_info.invoice_payload  # Выглядит как "donat_25_123456"

    # Достаем ID оффера (берем первые две части: donat и 25)
    parts = payload.split("_")
    offer_id = f"{parts[0]}_{parts[1]}"

    offer = OFFERS.get(offer_id)
    user_id = message.from_user.id

    if offer:
        cron_to_add = offer["cron"]
        stars_spent = offer["stars"]

        # Начисляем валюту (обязательно с await!)
        await database.add_balance(user_id, cron_to_add)

        # Логируем в базу
        await database.log_donation(user_id, payment_info.telegram_payment_charge_id, stars_spent, cron_to_add)

        await message.answer(
            f"✅ <b>Оплата прошла успешно!</b>\n"
            f"Вам начислено <b>{cron_to_add:,}</b> cron.\n"
            f"Спасибо за поддержку проекта!",
            parse_mode="HTML"
        )