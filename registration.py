import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from typing import Callable, Dict, Any, Awaitable
import database

class RegistrationMiddleware(BaseMiddleware):
    def __init__(self):
        # Очень простой кеш для забаненных (id: True)
        self.ban_cache = {}

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:

        user = data.get("event_from_user")

        if user and not user.is_bot:
            user_id = user.id
            
            try:
                # 1. Проверка на бан (сначала в кеше, потом в БД)
                if user_id in self.ban_cache or await database.is_user_banned(user_id):
                    self.ban_cache[user_id] = True # Запоминаем забаненного
                    return 

                # 2. Подготовка данных
                username = f"@{user.username}" if user.username else "Нет юзернейма"
                # Используем full_name вместо first_name для корректности
                name_mention = user.mention_html(user.full_name)

                # 3. Регистрация/Обновление
                # Совет: внутри register_or_update_user добавьте проверку, 
                # изменились ли данные, прежде чем делать UPDATE
                await database.register_or_update_user(user_id, username, name_mention)
                
            except Exception as e:
                logging.error(f"Ошибка в RegistrationMiddleware: {e}")
                # Если БД упала, лучше пропустить пользователя к хендлеру, 
                # чтобы бот не "умирал" совсем (на ваше усмотрение)

        return await handler(event, data)
