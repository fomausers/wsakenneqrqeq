from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

router = Router()

# Список триггеров для команды
HELP_COMMANDS = ["help", "помощь", "команды"]


@router.message(Command(*HELP_COMMANDS))
@router.message(F.text.lower().in_(HELP_COMMANDS))
async def help_command(message: Message):
    # URL вашей картинки
    photo_url = "https://example.com/your_image.jpg"  # Замените на реальную ссылку

    # Текст сообщения
    caption = (
        "<b>Навигация по командам бота</b>\n\n"
        "Здесь вы можете найти список всех доступных функций.\n"
        "Подробная помощь по навигации тут — @fm_modle_neew"
    )

    try:
        # Отправляем фото с подписью
        await message.answer_photo(
            photo=photo_url,
            caption=caption,
            parse_mode="HTML"
        )
    except Exception as e:
        # Если картинка не загрузится, отправим просто текст, чтобы бот не молчал
        await message.answer(caption, parse_mode="HTML")