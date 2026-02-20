from aiogram import Router, F
from aiogram.types import Message
import database

# Укажите здесь свой Telegram ID (можно узнать у @userinfobot)
ADMINS = [621856176, 987654321]

# Создаем роутер и сразу вешаем на него фильтр:
# он будет пропускать только сообщения от пользователей из списка ADMINS
router = Router()
router.message.filter(F.from_user.id.in_(ADMINS))


# Команда: выдать (Сумма) (ID)
@router.message(F.text.lower().startswith("выдать "))
async def admin_give_balance(message: Message):
    try:
        # Разбиваем сообщение по пробелам. Ожидаем: ["выдать", "100", "123456789"]
        args = message.text.split()
        if len(args) != 3:
            return await message.answer("⚠️ Использование: выдать [сумма] [ID]")

        amount = int(args[1])
        target_id = int(args[2])

        # Вызываем функцию из БД (мы её добавим ниже)
        success = await database.add_balance(target_id, amount)

        if success:
            await message.answer(f"✅ Пользователю {target_id} успешно выдано {amount} cron.")
        else:
            await message.answer(f"❌ Пользователь {target_id} не найден в базе.")

    except ValueError:
        await message.answer("⚠️ Ошибка! Сумма и ID должны быть числами.")


# Команда: бан (ID)
@router.message(F.text.lower().startswith("бан "))
async def admin_ban_user(message: Message):
    try:
        args = message.text.split()
        if len(args) != 2:
            return await message.answer("⚠️ Использование: бан [ID]")

        target_id = int(args[1])
        success = await database.set_ban_status(target_id, is_banned=True)

        if success:
            await message.answer(f"⛔️ Пользователь {target_id} заблокирован.")
        else:
            await message.answer(f"❌ Пользователь {target_id} не найден в базе.")

    except ValueError:
        await message.answer("⚠️ Ошибка! ID должен быть числом.")


# Команда: разбан (ID)
@router.message(F.text.lower().startswith("разбан "))
async def admin_unban_user(message: Message):
    try:
        args = message.text.split()
        if len(args) != 2:
            return await message.answer("⚠️ Использование: разбан [ID]")

        target_id = int(args[1])
        success = await database.set_ban_status(target_id, is_banned=False)

        if success:
            await message.answer(f"✅ Пользователь {target_id} разблокирован.")
        else:
            await message.answer(f"❌ Пользователь {target_id} не найден в базе.")

    except ValueError:
        await message.answer("⚠️ Ошибка! ID должен быть числом.")