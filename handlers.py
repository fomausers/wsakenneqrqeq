import time
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
import database

# Инициализируем роутер
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    # Формируем красивый текст приветствия
    text = (
        "👩‍💻 <a href='https://t.me/fmtestyybot'>modle | Чат-менеджер</a> приветствует Вас!\n\n"
        "💰 Я мини-игровой бот с мини играми.\n"
        "Во мне есть экономика и валюта.\n\n"
        "<i>Запуская бота, вы автоматически соглашаетесь с условиями использования.</i>"
    )

    # Создаем инлайн-кнопку со ссылкой для добавления в группу
    reply_markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="➕ Добавить бота в чат",
            url="https://t.me/fmtestyybot?startgroup=true"
        )
    ]])

    # Отправляем сообщение (disable_web_page_preview убирает огромную превьюшку от ссылки)
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )


# Реагируем на текст "б" или "Б" (без слеша)
@router.message(F.text.lower() == "б")
async def show_balance(message: Message):
    user_id = message.from_user.id

    # Достаем данные пользователя из БД
    user_data = await database.get_balance_and_mention(user_id)

    if user_data:
        balance, mention = user_data

        # --- ПРОВЕРКА БОНУСА ---
        current_time = int(time.time())
        last_bonus_time = await database.get_last_bonus(user_id)
        COOLDOWN_SECONDS = 24 * 60 * 60  # 24 часа

        reply_markup = None

        # Если прошло 24 часа — создаем кнопку
        if current_time - last_bonus_time >= COOLDOWN_SECONDS:
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🎁 Забрать бонус", callback_data="get_bonus")
            ]])

        # Формируем дизайн сообщения
        text = f"{mention}\n<b>🌕баланс: {balance} cron</b>"

        # Отправляем с кнопкой (если она создалась) или без неё
        await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)


# --- ОБРАБОТЧИК НАЖАТИЯ НА КНОПКУ БОНУСА ---
@router.callback_query(F.data == "get_bonus")
async def process_bonus_button(callback: CallbackQuery):
    user_id = callback.from_user.id
    current_time = int(time.time())

    COOLDOWN_SECONDS = 24 * 60 * 60
    BONUS_AMOUNT = 2500

    # Проверяем базу еще раз, чтобы игрок не нажал дважды
    last_bonus_time = await database.get_last_bonus(user_id)

    if current_time - last_bonus_time >= COOLDOWN_SECONDS:
        # Начисляем бонус и обновляем время
        await database.add_balance(user_id, BONUS_AMOUNT)
        await database.update_last_bonus(user_id, current_time)

        # Получаем новые данные с обновленным балансом
        user_data = await database.get_balance_and_mention(user_id)
        if user_data:
            balance, mention = user_data
            # Перерисовываем сообщение: убираем кнопку и добавляем текст о получении
            new_text = f"{mention}\n<b>🌕баланс: {balance} cron</b>\n\n<i>✅ Бонус {BONUS_AMOUNT} cron зачислен!</i>"
            await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)

        # Показываем всплывающее окно
        await callback.answer(f"Успешно получено {BONUS_AMOUNT} cron!", show_alert=True)
    else:
        # Если время не пришло (например, кто-то нажал на старую кнопку в чате)
        await callback.answer("Бонус пока недоступен!", show_alert=True)
        # Убираем старую кнопку
        await callback.message.edit_reply_markup(reply_markup=None)