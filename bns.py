import time
from aiogram import Router, F
from aiogram.types import Message
import database

router = Router()

BONUS_AMOUNT = 2500
COOLDOWN_SECONDS = 24 * 60 * 60  # 24 часа в секундах (86400)


@router.message(F.text.lower() == "бонус")
async def give_daily_bonus(message: Message):
    user_id = message.from_user.id

    # Получаем текущее время в секундах
    current_time = int(time.time())

    # Получаем время последнего бонуса из БД
    last_bonus_time = await database.get_last_bonus(user_id)

    # Считаем, сколько прошло времени с последнего взятия
    time_passed = current_time - last_bonus_time

    if time_passed >= COOLDOWN_SECONDS:
        # Прошло больше 24 часов — выдаем бонус
        await database.add_balance(user_id, BONUS_AMOUNT)
        await database.update_last_bonus(user_id, current_time)

        icon = database.get_currency_icon()

        # Получаем данные юзера для красивого обращения (чтобы стиль совпадал с командой "б")
        user_data = await database.get_balance_and_mention(user_id)
        mention = user_data[1] if user_data else message.from_user.first_name

        await message.answer(f"🎁 {mention}, ты успешно получил свой ежедневный бонус: <b>{BONUS_AMOUNT} {icon}</b>!",
                             parse_mode="HTML")
    else:
        # Прошло меньше 24 часов — считаем, сколько осталось
        time_left = COOLDOWN_SECONDS - time_passed
        hours = time_left // 3600
        minutes = (time_left % 3600) // 60

        await message.answer(
            f"⏳ Бонус уже был получен.\nСледующий будет доступен через <b>{hours} ч. {minutes} мин.</b>",
            parse_mode="HTML")