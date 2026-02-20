from aiogram import Router, F, Bot
from aiogram.types import Message
import database

router = Router()


def mention(user_id: int, name: str | None):
    # Вспомогательная функция для создания кликабельного имени
    name = name or "Пользователь"
    return f"<a href='tg://user?id={user_id}'>{name}</a>"


# Команда для перевода: п (сумма) [реплай или ID]
@router.message(F.text.lower().startswith("п "))
async def transfer_money(message: Message, bot: Bot):
    parts = message.text.split()

    if len(parts) < 2:
        return await message.answer("❌ Формат: п [сумма] [реплай] ИЛИ п [сумма] [ID]")

    try:
        amount = int(parts[1])
        if amount <= 0:
            return await message.answer("❌ Сумма должна быть больше 0.")
    except ValueError:
        return await message.answer("❌ Сумма должна быть числом.")

    from_user = message.from_user

    # === вариант с реплаем ===
    if message.reply_to_message:
        to_user = message.reply_to_message.from_user
        to_user_id = to_user.id
        to_user_name = to_user.first_name

    # === вариант с ID ===
    elif len(parts) == 3:
        try:
            to_user_id = int(parts[2])
            # Пытаемся получить инфу о пользователе через бота
            chat = await bot.get_chat(to_user_id)
            to_user_name = chat.first_name
        except Exception:
            return await message.answer("❌ Некорректный ID или бот не знает этого пользователя.")
    else:
        return await message.answer("❌ Используй реплай на сообщение игрока или укажи его ID.")

    # Проверка на перевод самому себе
    if from_user.id == to_user_id:
        return await message.answer("❌ Нельзя передавать cron самому себе.")

    # Делаем перевод через БД
    success, result_msg = await database.make_transfer(from_user.id, to_user_id, amount)

    if not success:
        return await message.answer(f"❌ Ошибка: {result_msg}")

    # Формируем красивые имена
    from_mention = mention(from_user.id, from_user.first_name)
    to_mention = mention(to_user_id, to_user_name)
    icon = database.get_currency_icon()

    await message.answer(
        f"💸 {from_mention} передал <b>{amount} {icon}</b> игроку {to_mention}",
        parse_mode="HTML"
    )

    # Пробуем отправить получателю уведомление в личку (сработает, если он запускал бота в ЛС)
    try:
        await bot.send_message(
            to_user_id,
            f"📥 {from_mention} перевел вам <b>{amount} {icon}</b>!",
            parse_mode="HTML"
        )
    except Exception:
        pass  # Если личка закрыта, просто игнорируем ошибку


# Команда для просмотра истории
@router.message(F.text.lower() == "история")
async def show_history(message: Message, bot: Bot):
    history = await database.get_transfer_history(message.from_user.id)
    icon = database.get_currency_icon()

    if not history:
        return await message.answer("📜 У вас еще нет истории переводов.")

    text = "📜 <b>Последние 10 переводов:</b>\n\n"

    for from_id, to_id, amount, date in history:
        # Если отправитель — мы
        if from_id == message.from_user.id:
            try:
                chat = await bot.get_chat(to_id)
                name = chat.first_name
            except Exception:
                name = "Игрок"

            text += f"➖ <i>{date}</i> | Вы отправили <b>{amount} {icon}</b> {mention(to_id, name)}\n"

        # Если получатель — мы
        else:
            try:
                chat = await bot.get_chat(from_id)
                name = chat.first_name
            except Exception:
                name = "Игрок"

            text += f"➕ <i>{date}</i> | Вы получили <b>{amount} {icon}</b> от {mention(from_id, name)}\n"

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)