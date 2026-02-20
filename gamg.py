import asyncio
import random
import re
from aiogram import Router, F
from aiogram.types import Message
import database

router = Router()

# Антифлуд: храним ID пользователей, чья игра еще не закончилась
active_games = set()

# Словарь с эмодзи для каждой игры
GAMES = {
    "кубик": "🎲",
    "баскет": "🏀",
    "дартс": "🎯",
    "боулинг": "🎳"
}


# Регулярное выражение ловит команды вида: кубик 100, баскет вб и т.д.
@router.message(F.text.regexp(re.compile(r"^(кубик|баскет|дартс|боулинг)\s+(\d+|вб)$", re.IGNORECASE)))
async def play_mini_game(message: Message):
    user_id = message.from_user.id

    # --- ЗАЩИТА ОТ АНТИФЛУДА ---
    if user_id in active_games:
        return await message.answer("⏳ Дождитесь результата текущей игры, прежде чем начать новую!")

    parts = message.text.lower().split()
    game_name = parts[0]
    bet_str = parts[1]

    # Получаем баланс и упоминание
    user_data = await database.get_balance_and_mention(user_id)
    if not user_data:
        return await message.answer("❌ Ошибка получения данных. Напишите /start")

    balance, mention = user_data

    # Определяем ставку
    if bet_str == "вб":
        bet = balance
    else:
        bet = int(bet_str)

    if bet <= 0:
        return await message.answer("❌ Ставка должна быть больше 0.")

    if balance < bet:
        return await message.answer("❌ Недостаточно cron на балансе!")

    # Блокируем пользователя для новых игр
    active_games.add(user_id)

    try:
        # Сразу списываем ставку с баланса
        await database.add_balance(user_id, -bet)

        # Отправляем анимированный эмодзи
        emoji = GAMES[game_name]
        dice_msg = await message.answer_dice(emoji=emoji)

        # Telegram сам генерирует результат (для кубика, дартса, боулинга это 1-6)
        # Для баскетбола 1-5 (поэтому 1-3 это мимо/штанга, а 4-5 попадание)
        value = dice_msg.dice.value

        # Ждем завершения анимации (примерно 4 секунды)
        await asyncio.sleep(4)

        # Логика: 1, 2, 3 - проигрыш; 4, 5, 6 - выигрыш
        if value <= 3:
            # Проигрыш (ничего не начисляем)
            win_amount = 0
            result_text = "проиграл"
        else:
            # Выигрыш (множитель от 1.3 до 2.0)
            multiplier = random.uniform(1.3, 2.0)
            win_amount = int(bet * multiplier)
            result_text = "выиграл"

            # Начисляем выигранную сумму
            await database.add_balance(user_id, win_amount)

        # Формируем итоговое сообщение строго по дизайну
        text = (
            f"{mention} {result_text}\n"
            f"🌕ставка: {bet}\n"
            f"💼выиграш: {win_amount}"
        )

        # Отправляем результат В ОТВЕТ на сообщение с эмодзи
        await dice_msg.reply(text, parse_mode="HTML")

    finally:
        # Обязательно снимаем блокировку в конце, даже если произошла ошибка
        active_games.discard(user_id)