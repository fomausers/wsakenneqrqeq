import asyncio
from aiogram import Bot, Dispatcher
import database
from handlers import router as main_router
from admyn import router as admin_router # Импортируем админский роутер
from registration import RegistrationMiddleware
from roulette import router as roulette_router
from bns import router as bonus_router
from donat import router as donat_router
from transfer import router as transfer_router
from gamg import router as gamg_router


BOT_TOKEN = "8535768087:AAF9D6Sm4hVIYGgaGLA9h8qGvrfSFI5hrmk"

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    await database.init_db()

    dp.update.middleware(RegistrationMiddleware())

    # ПОДКЛЮЧАЕМ РОУТЕРЫ
    dp.include_router(admin_router) # Админский лучше подключать первым
    dp.include_router(roulette_router)
    dp.include_router(bonus_router)
    dp.include_router(donat_router)
    dp.include_router(transfer_router)
    dp.include_router(gamg_router)
    dp.include_router(main_router)  # Пользовательский - вторым

    print("Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")