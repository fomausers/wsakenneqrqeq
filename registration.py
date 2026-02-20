from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable
import database


class RegistrationMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:

        user = data.get("event_from_user")

        if user:
            # --- ПРОВЕРКА НА БАН ---
            # Проверяем в БД, не забанен ли юзер.
            # Если да - просто прерываем обработку (return) и бот будет его игнорировать
            if await database.is_user_banned(user.id):
                return

            # Если не забанен - идем дальше по старой логике
            username = f"@{user.username}" if user.username else "Нет юзернейма"
            name_mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

            await database.register_or_update_user(user.id, username, name_mention)

        return await handler(event, data)