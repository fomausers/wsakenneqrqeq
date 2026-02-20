import aiosqlite
import datetime
import json
import time # <-- Добавили для работы со временем

DB_NAME = 'bot_database.db'

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # В таблицу users добавлено поле last_bonus INTEGER DEFAULT 0
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            reg_time TEXT,
            name_mention TEXT,
            is_banned BOOLEAN DEFAULT 0,
            daily_win INTEGER DEFAULT 0,
            last_bet TEXT,
            last_bonus INTEGER DEFAULT 0
        )''')
        # ... (остальные таблицы game_logs и chat_settings оставляем без изменений)
        await db.execute('''CREATE TABLE IF NOT EXISTS game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            win_num INTEGER,
            win_color TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS chat_settings (
            chat_id INTEGER PRIMARY KEY,
            games_enabled BOOLEAN DEFAULT 1
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS donations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    charge_id TEXT,
                    stars_spent INTEGER,
                    cron_added INTEGER,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS transfers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER,
                    receiver_id INTEGER,
                    amount INTEGER,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
        await db.commit()

# --- НОВЫЕ ФУНКЦИИ ДЛЯ БОНУСА ---

async def get_last_bonus(user_id: int) -> int:
    """Получает время последнего бонуса в секундах."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT last_bonus FROM users WHERE user_id = ?', (user_id,))
        res = await cursor.fetchone()
        return res[0] if res else 0

async def update_last_bonus(user_id: int, current_time: int):
    """Обновляет время получения бонуса."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET last_bonus = ? WHERE user_id = ?', (current_time, user_id))
        await db.commit()

# --- ФУНКЦИИ ДЛЯ РУЛЕТКИ ---

async def get_balance(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        res = await cursor.fetchone()
        return res[0] if res else 0

# (Твоя функция add_balance из прошлого шага должна остаться, она уже работает как нужно)

async def save_last_bet(user_id: int, items: list):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET last_bet = ? WHERE user_id = ?', (json.dumps(items), user_id))
        await db.commit()

async def get_last_bet(user_id: int) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT last_bet FROM users WHERE user_id = ?', (user_id,))
        res = await cursor.fetchone()
        if res and res[0]:
            return json.loads(res[0])
        return []

async def add_game_log(chat_id: int, win_num: int, win_color: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT INTO game_logs (chat_id, win_num, win_color) VALUES (?, ?, ?)', (chat_id, win_num, win_color))
        await db.commit()

async def get_game_logs(chat_id: int) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT win_num, win_color FROM game_logs WHERE chat_id = ? ORDER BY id DESC LIMIT 10', (chat_id,))
        return await cursor.fetchall()

def get_currency_icon() -> str:
    # Обычная функция (не асинхронная), так как она просто отдает текст
    return "cron"

async def add_daily_win(user_id: int, win_amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET daily_win = daily_win + ? WHERE user_id = ?', (win_amount, user_id))
        await db.commit()

async def is_games_enabled(chat_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT games_enabled FROM chat_settings WHERE chat_id = ?', (chat_id,))
        res = await cursor.fetchone()
        return bool(res[0]) if res else True

# ... здесь остаются ваши старые функции register_or_update_user и get_balance_and_mention ...

# --- НОВЫЕ ФУНКЦИИ ДЛЯ АДМИНКИ ---

async def add_balance(user_id: int, amount: int) -> bool:
    """Добавляет баланс. Возвращает True, если юзер найден, иначе False."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        user = await cursor.fetchone()
        if user is None:
            return False

        await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        await db.commit()
        return True


async def set_ban_status(user_id: int, is_banned: bool) -> bool:
    """Устанавливает статус бана. Возвращает True, если юзер найден."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if await cursor.fetchone() is None:
            return False

        # SQLite хранит boolean как 0 и 1
        ban_val = 1 if is_banned else 0
        await db.execute('UPDATE users SET is_banned = ? WHERE user_id = ?', (ban_val, user_id))
        await db.commit()
        return True


async def is_user_banned(user_id: int) -> bool:
    """Проверяет, забанен ли пользователь."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
        result = await cursor.fetchone()
        if result and result[0] == 1:
            return True
        return False



async def register_or_update_user(user_id: int, username: str, name_mention: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT username, name_mention FROM users WHERE user_id = ?', (user_id,))
        user = await cursor.fetchone()

        if user is None:
            # Пользователя нет в базе — регистрируем
            reg_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await db.execute('''INSERT INTO users (user_id, username, reg_time, name_mention)
                                VALUES (?, ?, ?, ?)''', (user_id, username, reg_time, name_mention))
        else:
            # Пользователь есть — проверяем, не сменил ли он юзернейм или имя
            current_username, current_mention = user
            if current_username != username or current_mention != name_mention:
                await db.execute('''UPDATE users SET username = ?, name_mention = ? WHERE user_id = ?''',
                                 (username, name_mention, user_id))
        await db.commit()

async def get_balance_and_mention(user_id: int):
    # Получаем баланс и упоминание для команды "б"
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT balance, name_mention FROM users WHERE user_id = ?', (user_id,))
        return await cursor.fetchone()


# 2. Добавь эти новые функции в конец файла:
async def make_transfer(from_id: int, to_id: int, amount: int) -> tuple[bool, str]:
    """Выполняет перевод средств, если хватает баланса и получатель есть в базе."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Проверяем баланс отправителя
        cursor = await db.execute('SELECT balance FROM users WHERE user_id = ?', (from_id,))
        sender = await cursor.fetchone()

        if not sender or sender[0] < amount:
            return False, "Недостаточно средств."

        # Проверяем, существует ли получатель в базе
        cursor = await db.execute('SELECT user_id FROM users WHERE user_id = ?', (to_id,))
        if not await cursor.fetchone():
            return False, "Получатель не найден в базе бота. Он должен хотя бы раз написать боту."

        # Выполняем перевод
        await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, from_id))
        await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, to_id))

        # Логируем в историю (сохраняем дату)
        await db.execute('INSERT INTO transfers (sender_id, receiver_id, amount) VALUES (?, ?, ?)',
                         (from_id, to_id, amount))
        await db.commit()

        return True, "Успешно"


async def get_transfer_history(user_id: int) -> list:
    """Возвращает 10 последних переводов пользователя."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Получаем переводы, где юзер либо отправитель, либо получатель. Берем только дату (без секунд)
        cursor = await db.execute('''
            SELECT sender_id, receiver_id, amount, DATE(date) 
            FROM transfers 
            WHERE sender_id = ? OR receiver_id = ? 
            ORDER BY id DESC LIMIT 10
        ''', (user_id, user_id))
        return await cursor.fetchall()




async def log_donation(user_id: int, charge_id: str, stars_spent: int, cron_added: int):
    """Логирует успешную покупку за Stars"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'INSERT INTO donations (user_id, charge_id, stars_spent, cron_added) VALUES (?, ?, ?, ?)',
            (user_id, charge_id, stars_spent, cron_added)
        )
        await db.commit()
