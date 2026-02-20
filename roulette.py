import re
import random
import asyncio
import time
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram import html

from database import (
    get_balance, add_balance, save_last_bet, get_last_bet,
    add_game_log, get_game_logs, get_currency_icon, add_daily_win, is_games_enabled
)

router = Router()
games = {}
user_locks = {}
chat_locks = {}
RED_NUMBERS = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]


def get_styled_mention(user):
    return f'<b><a href="tg://user?id={user.id}">{html.quote(user.full_name)}</a></b>'


def get_color(n):
    if n == 0: return "🟢"
    return "🔴" if n in RED_NUMBERS else "⚫"


@router.message(
    F.chat.type != "private",
    F.text.regexp(re.compile(r"^(лог|ставки|отмена|отменить|\d+)", re.IGNORECASE))
)
async def handle_bets(message: Message):
    # Проверка: включены ли игры в группе (ДОБАВЛЕН await)
    if not await is_games_enabled(message.chat.id):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    text_parts = message.text.lower().split()

    if not text_parts:
        return

    command = text_parts[0]
    game = games.setdefault(chat_id, {"bets": {}, "start_time": 0, "is_running": False})

    # --- КОМАНДА ЛОГ ---
    if command == "лог":
        # ДОБАВЛЕН await
        logs = await get_game_logs(chat_id)
        if not logs:
            return await message.answer("История игр пуста")
        # Вывод в стиле блокнота (blockquote)
        res = "\n".join([f"<b>{n}</b> {c}" for n, c in logs[:10]])
        return await message.answer(f"<b>Последние игры:</b>\n<blockquote>{res}</blockquote>", parse_mode="HTML")

    if game["is_running"]:
        return

    # Создаем или получаем замок для пользователя (защита от двойных нажатий/сообщений)
    lock = user_locks.setdefault(user_id, asyncio.Lock())

    # --- КОМАНДА СТАВКИ (просмотр текущих) ---
    if command == "ставки":
        if user_id not in game["bets"]:
            return await message.answer("У вас нет активных ставок.")

        user_data = game["bets"][user_id]
        user_bets = user_data["items"]
        mention = user_data["mention"]

        # Формат: Ник 10000 на RED
        lines = [f"{mention} {b['amount']} на {b['display']}" for b in user_bets]

        if len("\n".join(lines)) > 4000:
            for i in range(0, len(lines), 30):
                chunk = lines[i:i + 30]
                await message.answer("\n".join(chunk), parse_mode="HTML")
        else:
            await message.answer("\n".join(lines), parse_mode="HTML")
        return

    async with lock:
        # --- КОМАНДА ОТМЕНА ---
        if command in ["отмена", "отменить"]:
            if user_id in game["bets"]:
                total_return = sum(bet['amount'] for bet in game["bets"][user_id]["items"])
                mention = game["bets"][user_id]["mention"]

                # Здесь await НЕ НУЖЕН, функция просто возвращает строку
                icon = get_currency_icon()

                # ДОБАВЛЕН await
                await add_balance(user_id, total_return)
                del game["bets"][user_id]

                if not game["bets"]:
                    game["start_time"] = 0

                return await message.answer(f"{mention}, ставки отменены. Возвращено: {total_return} {icon}",
                                            parse_mode="HTML")
            return await message.answer("У вас нет активных ставок.")

        # --- ПРИЕМ СТАВОК (если команда — число) ---
        if command.isdigit():
            amount = int(command)
            if amount <= 0:
                return

            args = text_parts[1:]
            if not args:
                return

            if len(args) > 100:
                await message.reply("Максимум 100 ставок за сообщение.")
                args = args[:100]

            # ДОБАВЛЕН await
            user_balance = await get_balance(user_id)
            # Здесь await НЕ НУЖЕН
            icon = get_currency_icon()

            if user_balance < amount:
                return await message.reply(f"Недостаточно {icon}!")

            temp_new_bets = []
            for arg in args:
                # Цвета и Зеро
                if arg in ['к', 'красное', 'red']:
                    temp_new_bets.append({"type": "red", "amount": amount, "display": "RED"})
                elif arg in ['ч', 'черное', 'black']:
                    temp_new_bets.append({"type": "black", "amount": amount, "display": "BLACK"})
                elif arg in ['з', 'зеленое', 'zero', '0']:
                    temp_new_bets.append({"type": "number", "amount": amount, "value": 0, "display": "ZERO"})
                # Диапазоны (например 1-12)
                elif '-' in arg:
                    try:
                        s_raw, e_raw = map(int, arg.split('-'))
                        s, e = sorted([s_raw, e_raw])
                        if 0 <= s <= 36 and 0 <= e <= 36:
                            temp_new_bets.append(
                                {"type": "range", "amount": amount, "value": (s, e), "display": f"{s}-{e}"})
                    except:
                        continue
                # Числа
                elif arg.isdigit():
                    n = int(arg)
                    if 1 <= n <= 36:
                        temp_new_bets.append({"type": "number", "amount": amount, "value": n, "display": str(n)})

            if not temp_new_bets:
                return

            total_cost = len(temp_new_bets) * amount

            # Проверка, хватит ли денег на все аргументы (например 100 к ч з)
            if user_balance < total_cost:
                can_afford = user_balance // amount
                temp_new_bets = temp_new_bets[:can_afford]
                total_cost = len(temp_new_bets) * amount

            if not temp_new_bets:
                return await message.reply(f"Недостаточно {icon}!")

            # Списываем баланс (ДОБАВЛЕН await)
            await add_balance(user_id, -total_cost)

            mention = get_styled_mention(message.from_user)
            user_game_data = game["bets"].setdefault(user_id, {"items": [], "mention": mention})
            user_game_data["items"].extend(temp_new_bets)

            # Таймер до начала рулетки (15 секунд после первой ставки)
            if game["start_time"] == 0:
                game["start_time"] = time.time() + 15

            # Формирование строк подтверждения (без лишних значков, в одну строку)
            confirm_lines = [f"Ставка принята: {mention} {amount} {icon} на {b['display']}" for b in temp_new_bets]

            if len(confirm_lines) <= 10:
                await message.answer("\n".join(confirm_lines), parse_mode="HTML")
            else:
                # Если ставок много — шлем частями, чтобы не спамить
                for i in range(0, len(confirm_lines), 20):
                    chunk = confirm_lines[i:i + 20]
                    await message.answer("\n".join(chunk), parse_mode="HTML")
                    await asyncio.sleep(0.3)


@router.message(F.text.lower() == "го", F.chat.type != "private")
async def start_roulette(message: Message, bot: Bot):
    chat_id = message.chat.id

    # 1. Проверка: включены ли игры (ДОБАВЛЕН await)
    if not await is_games_enabled(chat_id):
        return

    # 2. Проверка: есть ли вообще ставки в этом чате
    if chat_id not in games or not games[chat_id]["bets"]:
        return
    game = games[chat_id]

    # 3. Проверка: не запущена ли уже рулетка (Lock)
    chat_lock = chat_locks.setdefault(chat_id, asyncio.Lock())
    if chat_lock.locked():
        return

    # 4. Проверка: запуск разрешен только участнику игры
    if message.from_user.id not in game["bets"]:
        return await message.reply("❌ Вы не можете запустить рулетку, так как не сделали ставку!")

    # 5. Проверка: не рано ли запускать (таймер 15 сек)
    remaining = game["start_time"] - time.time()
    if remaining > 0:
        return await message.answer(f"⏳ Осталось еще {int(remaining)} сек.")

    async with chat_lock:
        game["is_running"] = True

        # --- ГЕНЕРАЦИЯ РЕЗУЛЬТАТА ---
        win_num = random.randint(0, 36)
        win_color = get_color(win_num)
        # Эмодзи шарика для заголовка
        ball_emoji = "🟢" if win_num == 0 else ("🔴" if win_color == "🔴" else "⚫")

        # ДОБАВЛЕН await
        await add_game_log(chat_id, win_num, win_color)

        # await не нужен (возвращает просто строку)
        icon = get_currency_icon()

        all_lines = []
        winners_summary = []

        # --- РАСЧЕТ ВЫИГРЫШЕЙ ---
        for u_id, user_data in game["bets"].items():
            mention = user_data["mention"]
            total_win = 0

            # ДОБАВЛЕН await
            await save_last_bet(u_id, user_data["items"])  # Для кнопок повтора

            for b in user_data["items"]:
                # Суммы пишем слитно (10000)
                amount_val = b['amount']
                all_lines.append(f"{mention} {amount_val} {icon} на {b['display']}")

                win = False
                mult = 0

                # Логика выигрыша
                if b["type"] == "red" and win_color == "🔴":
                    mult = 2
                    win = True
                elif b["type"] == "black" and win_color == "⚫":
                    mult = 2
                    win = True
                elif b["type"] == "number" and b["value"] == win_num:
                    mult = 36
                    win = True
                elif b["type"] == "range":
                    start, end = b["value"]
                    if start <= win_num <= end:
                        diff = end - start + 1
                        # Множитель с учетом комиссии системы (0.98)
                        mult = (36 / diff) * 0.98
                        win = True

                if win:
                    win_amt = int(amount_val * mult)
                    total_win += win_amt
                    winners_summary.append(
                        f"{mention} выиграл {win_amt} {icon} на {b['display']}"
                    )

            if total_win > 0:
                # ДОБАВЛЕНЫ await
                await add_balance(u_id, total_win)
                await add_daily_win(u_id, total_win)

        # --- АНИМАЦИЯ (СТИКЕРЫ) ---
        sticker_map = {
            0: "CAACAgIAAxkBAAEQXcBpeqZEgxEU2tiUPeyDBIRXEnHYSQACMXEAAsGPqEvgtLCZn60BCTgE",
            1: "CAACAgIAAxkBAAEQXbJpeoOHpIEOtz18xXYtUmm0TmdAiQACYm0AAsV_qUvwV2I-O_92MzgE",
            2: "CAACAgIAAxkBAAEQYANpe9F6lzrE8IFbnhectUO2LoTM3QACu3AAAmt8qUuMHj22bDK7hDgE",
            3: "CAACAgIAAxkBAAEQX_Npe9F1lP4qfS3rAAGpODj0GZqdx40AAn9rAAKGzalL-TYQexywcy04BA",
            4: "CAACAgIAAxkBAAEQX-Jpe9Dx0qYPYLRF7DBLoy2cZWEnagACGWwAAgmWqEvDac6OXAABYnY4BA",
            5: "CAACAgIAAxkBAAEQYAlpe9F7qr1p3Woo50XN-XItV4aVOQACaG8AAvZ0qUs10WCEkqxX3DgE",
            6: "CAACAgIAAxkBAAEQX9hpe9CWu5vOlGy62cPPJb2bquJ3jgACInAAAkkgqUum3rYhVGMOYzgE",
            7: "CAACAgIAAxkBAAEQX9Bpe9BL5vM6ApenT43CWRN86gNGvgACpmUAAgxQsEvOOrqMWzDs9zgE",
            8: "CAACAgIAAxkBAAEQX9xpe9C5onkGvqIFItLSRGtAYMtDAQACc2kAAo0yqUsreLPxA-J-aTgE",
            9: "CAACAgIAAxkBAAEQX9Zpe9CCpQaRgDCxhEtTj7lKSO8VcAACg2YAArU-qUvBsA5QppMYBDgE",
            10: "CAACAgIAAxkBAAEQX_Zpe9F2AUWtvi-MOcQbQwzwOnifUwACCGwAAn9KqEtl9f_8GfnALDgE",
            11: "CAACAgIAAxkBAAEQX_1pe9F4qoUGFhHbKM1_Jc-EX_7mAwAC3msAAjl-qUtgCWpsiik4pDgE",
            12: "CAACAgIAAxkBAAEQXbBpeoJy-Gyw8EDx2wLa6xaUKdSdYwACc3cAAqZkqEsZBYHZtb4HsDgE",
            13: "CAACAgIAAxkBAAEQX85pe9A-BxpfX8EoImybMJxPXQTHRQAC9WUAAqUtsEu4A_dYVBl3EzgE",
            14: "CAACAgIAAxkBAAEQX9Jpe9BhUv8NPxt3iLNg_3mp5ZxsgAACaHUAAm06qUubaUhHHkRQtDgE",
            15: "CAACAgIAAxkBAAEQX-Rpe9EbwURz37Sw5b9zlpc9amOhFwACXnIAArg5qUueqto_IaZInTgE",
            16: "CAACAgIAAxkBAAEQX_ppe9F3o3Y54Czv8Jhk7rttFbh3qQAC3nQAAl2LqEti203L-GHZ8TgE",
            17: "CAACAgIAAxkBAAEQXb5peqYTsUL_gKXumjlD3-QDGqCJFAAC-XEAA8qoSzy-pE02t_7DOAQ",
            18: "CAACAgIAAxkBAAEQX_Rpe9F24unPigvU8JI-dG59acsH_gACu3EAApaoqUt4-NurUHdQCzgE",
            19: "CAACAgIAAxkBAAEQYAJpe9F62oiZaZRyzPMAAfM294r1akEAAtNvAAIUb6hLOIQHWBKuvrA4BA",
            20: "CAACAgIAAxkBAAEQX-ppe9EhbvY6sGHd1Hw6iTdwSPCsyQACmmMAAn-tqUuIolA0hUdGuzgE",
            21: "CAACAgIAAxkBAAEQX-hpe9EgyqfP7uE02yuiJYrjtNIZtQACDnkAAkJhqEsh2VgC776rRTgE",
            22: "CAACAgIAAxkBAAEQX9Rpe9Bxu4-hyiR5M9pZc2ZSPsSlLQAConUAAlt4qEue2yWiPIl8RTgE",
            23: "CAACAgIAAxkBAAEQX_lpe9F327-dKhLw7mw99TnbTlvEHwACxXEAAnmNqEsZVFvH7_y5lzgE",
            24: "CAACAgIAAxkBAAEQWvNpeUApDbVYFbfaye8zFvoRC1DVLgAC4nkAArFxsEu3KApsLo6nfDgE",
            25: "CAACAgIAAxkBAAEQX-Zpe9Ee-pGvirreqG6q7MoHkp4q0AACf3MAAkiqqUt2dUbW8-Qg9DgE",
            26: "CAACAgIAAxkBAAEQX8xpe9AwHt_q_vRcDictDW92cZnfqQACPmsAAv_5sUuGhpKQfUxwwDgE",
            27: "CAACAgIAAxkBAAEQX_9pe9F59AABiZ15ygNuaPsxr4FgSsIAAj1tAAKY9ahL8AhjC7wZ8W04BA",
            28: "CAACAgIAAxkBAAEQX8ppe9AbSlOQyF_RpPLLJI1l0McRPQACu2wAAiUkqEsTMHlkQoOOyzgE",
            29: "CAACAgIAAxkBAAEQX-xpe9EjeQdTk3RmXWb8M3AbNhiIWgAC324AAh7VqUte0Uc3aofKwzgE",
            30: "CAACAgIAAxkBAAEQX-5pe9FrGJrnujiib6kozWfO9W7Q_gAC3G0AAjoGsEumvpK88ed0uzgE",
            31: "CAACAgIAAxkBAAEQX_tpe9F3FO3594A2ekuO95jiPCERvAACFm8AAmRmqUvFyBdW_r3jBDgE",
            32: "CAACAgIAAxkBAAEQYAZpe9F7gnfFVNHrVLYOFCOC7IgvmQACY3EAAlBCsUunVsFT9ROxzzgE",
            33: "CAACAgIAAxkBAAEQYAVpe9F6B3Ie5WBEOIlYEIZ8xmdu5wACUXIAAiibsUu7t8mandGQuTgE",
            34: "CAACAgIAAxkBAAEQX-Bpe9Dt-43xw98RnE75FDiv_16Q2gACaXcAAq6jsUsGQj_3FSUlEzgE",
            35: "CAACAgIAAxkBAAEQYAABaXvReTMUZX4z8Ih4jYPTodALsrMAAr1oAALNl6hLC2JQEDSBpQ04BA",
            36: "CAACAgIAAxkBAAEQX95pe9DSuhvn43e6FY_Yin-ySANqpAACUW8AAi9JqEuBxymhD-OS3TgE"
        }

        s_id = sticker_map.get(win_num)
        if s_id:
            try:
                sticker_msg = await message.answer_sticker(s_id)
                await asyncio.sleep(4.5)
                try:
                    await bot.delete_message(chat_id, sticker_msg.message_id)
                except:
                    pass
            except:
                await asyncio.sleep(2)

        # --- ЗАВЕРШЕНИЕ И ВЫВОД ---
        games.pop(chat_id, None)

        header = f"<b>Результаты рулетки: {win_num} {ball_emoji}</b>\n\n"

        # Секция со всеми ставками (Убраны <blockquote>)
        bets_text = "<b>Ставки:</b>\n" + "\n".join(all_lines) + "\n\n"

        # Секция с победителями (Убраны <blockquote>)
        win_text = "<b>Победители:</b>\n"
        win_text += "\n".join(winners_summary) if winners_summary else "Никто не выиграл"

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Повторить", callback_data="rebet"),
            InlineKeyboardButton(text="Удвоить", callback_data="double")
        ]])

        await message.answer(header + bets_text + win_text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.in_(["rebet", "double"]))
async def fast_rebet_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    icon = get_currency_icon()

    last_bets = await get_last_bet(user_id)  # <-- Добавлен await
    if not last_bets:
        return await callback.answer("Нет прошлых ставок!", show_alert=True)

    multiplier = 2 if callback.data == "double" else 1
    total_cost = sum(b['amount'] for b in last_bets) * multiplier

    if await get_balance(user_id) < total_cost:  # <-- Добавлен await
        return await callback.answer("Недостаточно средств!", show_alert=True)

    game = games.setdefault(chat_id, {"bets": {}, "start_time": 0, "is_running": False})
    if game["is_running"]:
        return await callback.answer("Рулетка уже крутится!", show_alert=True)

    await add_balance(user_id, -total_cost)  # <-- Добавлен await
    mention = get_styled_mention(callback.from_user)
    u_data = game["bets"].setdefault(user_id, {"mention": mention, "items": []})

    if game["start_time"] == 0: game["start_time"] = time.time() + 15

    lines = []
    for b in last_bets:
        new_amt = b['amount'] * multiplier
        u_data["items"].append({
            "type": b["type"], "amount": new_amt, "display": b["display"], "value": b.get("value")
        })
        lines.append(f"<b>{b['display']}</b> — {new_amt} {icon}")

    title = f"{mention} повторил ставки:" if multiplier == 1 else f"{mention} удвоил ставки:"
    await callback.answer("Ставки приняты!")

    # Отправляем сообщение без тегов <blockquote>
    await callback.message.answer(f"{title}\n" + "\n".join(lines), parse_mode="HTML")