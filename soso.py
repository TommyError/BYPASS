import asyncio
import sqlite3
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv("8357573814:AAEzn5-67iylGo-U90YAIgFqgONyWfs97PE")
ADMIN_ID = int(os.getenv("479062582"))  # Ваш ID в Telegram
CHANNEL_ID = os.getenv(""-1479062582, "")  # ID канала для публикаций

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния FSM
class Form(StatesGroup):
    waiting_for_category_name = State()
    waiting_for_account_name = State()
    waiting_for_account_description = State()
    waiting_for_account_price = State()
    waiting_for_account_quantity = State()
    waiting_for_account_data = State()
    waiting_for_category_for_account = State()
    waiting_for_support_message = State()

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    
    # Таблица категорий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')
    
    # Таблица аккаунтов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            quantity INTEGER DEFAULT 1,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')
    
    # Таблица покупок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            account_id INTEGER NOT NULL,
            account_name TEXT,
            price REAL NOT NULL,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Функции для работы с БД
def get_categories():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cursor.fetchall()
    conn.close()
    return categories

def get_accounts_by_category(category_id):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, description, price, quantity 
        FROM accounts 
        WHERE category_id = ? AND quantity > 0
        ORDER BY name
    ''', (category_id,))
    accounts = cursor.fetchall()
    conn.close()
    return accounts

def get_account(account_id):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM accounts WHERE id = ?', (account_id,))
    account = cursor.fetchone()
    conn.close()
    return account

def update_account_quantity(account_id):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE accounts SET quantity = quantity - 1 WHERE id = ?', (account_id,))
    conn.commit()
    conn.close()

def record_purchase(user_id, username, account_id, account_name, price):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO purchases (user_id, username, account_id, account_name, price)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, account_id, account_name, price))
    conn.commit()
    conn.close()

def add_category(name):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def add_account(category_id, name, description, price, quantity, data):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO accounts (category_id, name, description, price, quantity, data)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (category_id, name, description, price, quantity, data))
    conn.commit()
    conn.close()

# Клавиатуры
def main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Каталог"), KeyboardButton(text="📦 Мои покупки")],
            [KeyboardButton(text="ℹ️ Помощь"), KeyboardButton(text="📞 Поддержка")]
        ],
        resize_keyboard=True
    )
    return keyboard

def admin_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить категорию"), KeyboardButton(text="➕ Добавить аккаунт")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="⬅️ В главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard

def categories_keyboard():
    categories = get_categories()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    row = []
    for cat_id, cat_name in categories:
        row.append(InlineKeyboardButton(text=cat_name, callback_data=f"cat_{cat_id}"))
        if len(row) == 2:
            keyboard.inline_keyboard.append(row)
            row = []
    
    if row:
        keyboard.inline_keyboard.append(row)
    
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])
    return keyboard

def accounts_keyboard(category_id):
    accounts = get_accounts_by_category(category_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for acc_id, name, description, price, quantity in accounts:
        btn_text = f"{name} - {price}₽ ({quantity} шт.)"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"acc_{acc_id}")
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data="back_to_categories")
    ])
    return keyboard

def buy_keyboard(account_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Купить", callback_data=f"buy_{account_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_accounts")]
    ])
    return keyboard

# Хендлеры
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Приветственное сообщение
    welcome_text = """
    👋 Добро пожаловать в магазин аккаунтов Telegram!

    🛒 <b>Каталог</b> - просмотр доступных аккаунтов
    📦 <b>Мои покупки</b> - история ваших покупок
    ℹ️ <b>Помощь</b> - инструкция по использованию
    📞 <b>Поддержка</b> - связь с администратором

    Выберите нужный пункт в меню ниже 👇
    """
    
    await message.answer(welcome_text, reply_markup=main_menu(), parse_mode="HTML")
    
    # Отправляем уведомление админу о новом пользователе
    if user_id != ADMIN_ID:
        admin_notification = f"🆕 Новый пользователь:\nID: {user_id}\nUsername: @{message.from_user.username}\nИмя: {message.from_user.full_name}"
        await bot.send_message(ADMIN_ID, admin_notification)

@dp.message(F.text == "🛒 Каталог")
async def show_catalog(message: types.Message):
    categories = get_categories()
    if not categories:
        await message.answer("Категории пока пусты. Ожидайте поступления товаров.")
        return
    
    text = "📂 <b>Выберите категорию:</b>"
    await message.answer(text, reply_markup=categories_keyboard(), parse_mode="HTML")

@dp.message(F.text == "📦 Мои покупки")
async def show_purchases(message: types.Message):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT account_name, price, purchase_date 
        FROM purchases 
        WHERE user_id = ? 
        ORDER BY purchase_date DESC
    ''', (message.from_user.id,))
    purchases = cursor.fetchall()
    conn.close()
    
    if not purchases:
        await message.answer("У вас пока нет покупок.")
        return
    
    text = "📦 <b>Ваши покупки:</b>\n\n"
    for i, (account_name, price, date) in enumerate(purchases, 1):
        date_str = datetime.strptime(date, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
        text += f"{i}. {account_name}\n   💰 {price}₽\n   📅 {date_str}\n\n"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "ℹ️ Помощь")
async def show_help(message: types.Message):
    help_text = """
    <b>❓ Как пользоваться магазином:</b>

    1. Нажмите <b>"🛒 Каталог"</b>
    2. Выберите категорию
    3. Выберите нужный аккаунт
    4. Нажмите <b>"✅ Купить"</b>
    5. После покупки вы получите данные аккаунта

    <b>⚠️ Важно:</b>
    • После покупки данные аккаунта придут вам в личные сообщения
    • Сохраните данные в надежном месте
    • Для замены аккаунта обратитесь в поддержку
    • Возврат средств только при технических проблемах

    <b>📞 Поддержка:</b> @ваш_логин
    """
    await message.answer(help_text, parse_mode="HTML")

@dp.message(F.text == "📞 Поддержка")
async def support_request(message: types.Message, state: FSMContext):
    await message.answer("📝 Напишите ваше сообщение для поддержки:")
    await state.set_state(Form.waiting_for_support_message)

@dp.message(Form.waiting_for_support_message)
async def process_support_message(message: types.Message, state: FSMContext):
    user_info = f"Пользователь: @{message.from_user.username}\nID: {message.from_user.id}\nИмя: {message.from_user.full_name}"
    support_text = f"📬 <b>Новое сообщение от пользователя:</b>\n\n{user_info}\n\n💬 Сообщение:\n{message.text}"
    
    # Отправляем админу
    await bot.send_message(ADMIN_ID, support_text, parse_mode="HTML")
    
    await message.answer("✅ Ваше сообщение отправлено администратору. Ожидайте ответа в ближайшее время.", reply_markup=main_menu())
    await state.clear()

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    
    stats_text = await get_stats()
    await message.answer(f"👑 <b>Админ-панель</b>\n\n{stats_text}", reply_markup=admin_menu(), parse_mode="HTML")

@dp.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет доступа.")
        return
    
    stats_text = await get_stats()
    await message.answer(stats_text, parse_mode="HTML")

@dp.message(F.text == "➕ Добавить категорию")
async def add_category_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer("Введите название новой категории:")
    await state.set_state(Form.waiting_for_category_name)

@dp.message(Form.waiting_for_category_name)
async def process_category_name(message: types.Message, state: FSMContext):
    if add_category(message.text):
        await message.answer(f"✅ Категория '{message.text}' добавлена!", reply_markup=admin_menu())
    else:
        await message.answer(f"❌ Категория '{message.text}' уже существует!", reply_markup=admin_menu())
    await state.clear()

@dp.message(F.text == "➕ Добавить аккаунт")
async def add_account_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    categories = get_categories()
    if not categories:
        await message.answer("❌ Сначала создайте категорию!", reply_markup=admin_menu())
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for cat_id, cat_name in categories:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=cat_name, callback_data=f"add_acc_cat_{cat_id}")
        ])
    
    await message.answer("Выберите категорию для аккаунта:", reply_markup=keyboard)
    await state.set_state(Form.waiting_for_category_for_account)

@dp.callback_query(F.data.startswith("add_acc_cat_"))
async def process_account_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[-1])
    await state.update_data(category_id=category_id)
    await callback.message.answer("Введите название аккаунта:")
    await state.set_state(Form.waiting_for_account_name)
    await callback.answer()

@dp.message(Form.waiting_for_account_name)
async def process_account_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание аккаунта:")
    await state.set_state(Form.waiting_for_account_description)

@dp.message(Form.waiting_for_account_description)
async def process_account_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите цену аккаунта (только число):")
    await state.set_state(Form.waiting_for_account_price)

@dp.message(Form.waiting_for_account_price)
async def process_account_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)
        await message.answer("Введите количество аккаунтов (число):")
        await state.set_state(Form.waiting_for_account_quantity)
    except ValueError:
        await message.answer("❌ Введите корректную цену (число):")

@dp.message(Form.waiting_for_account_quantity)
async def process_account_quantity(message: types.Message, state: FSMContext):
    try:
        quantity = int(message.text)
        await state.update_data(quantity=quantity)
        await message.answer("Введите данные аккаунта (логин:пароль или другие данные):")
        await state.set_state(Form.waiting_for_account_data)
    except ValueError:
        await message.answer("❌ Введите корректное количество (целое число):")

@dp.message(Form.waiting_for_account_data)
async def process_account_data(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    add_account(
        data['category_id'],
        data['name'],
        data['description'],
        data['price'],
        data['quantity'],
        message.text
    )
    
    await message.answer(f"✅ Аккаунт '{data['name']}' успешно добавлен!", reply_markup=admin_menu())
    await state.clear()

@dp.message(F.text == "⬅️ В главное меню")
async def back_to_main(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main_menu())

@dp.callback_query(F.data.startswith("cat_"))
async def show_category_accounts(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    accounts = get_accounts_by_category(category_id)
    
    if not accounts:
        await callback.message.edit_text("В этой категории пока нет аккаунтов.")
        await callback.answer()
        return
    
    category_name = ""
    for cat_id, cat_name in get_categories():
        if cat_id == category_id:
            category_name = cat_name
            break
    
    text = f"📁 <b>{category_name}</b>\n\nВыберите аккаунт:"
    await callback.message.edit_text(text, reply_markup=accounts_keyboard(category_id), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("acc_"))
async def show_account_details(callback: CallbackQuery):
    account_id = int(callback.data.split("_")[1])
    account = get_account(account_id)
    
    if not account:
        await callback.answer("Аккаунт не найден!")
        return
    
    acc_id, cat_id, name, description, price, quantity, data, created_at = account
    
    text = f"""
<b>{name}</b>

📝 <b>Описание:</b>
{description}

💰 <b>Цена:</b> {price}₽
📦 <b>В наличии:</b> {quantity} шт.
📅 <b>Добавлен:</b> {created_at[:10]}
    """
    
    await callback.message.edit_text(text, reply_markup=buy_keyboard(account_id), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def process_purchase(callback: CallbackQuery):
    account_id = int(callback.data.split("_")[1])
    account = get_account(account_id)
    
    if not account or account[5] <= 0:  # account[5] = quantity
        await callback.answer("❌ Аккаунт закончился!", show_alert=True)
        return
    
    acc_id, cat_id, name, description, price, quantity, data, created_at = account
    
    # Обновляем количество
    update_account_quantity(account_id)
    
    # Записываем покупку
    user = callback.from_user
    record_purchase(user.id, user.username, acc_id, name, price)
    
    # Отправляем данные аккаунта пользователю
    purchase_success = f"""
✅ <b>Покупка успешна!</b>

🎮 <b>Аккаунт:</b> {name}
💰 <b>Цена:</b> {price}₽
📅 <b>Дата покупки:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>Данные аккаунта:</b>
<code>{data}</code>

⚠️ <b>Сохраните эти данные в надежном месте!</b>
    """
    
    await callback.message.delete()
    await bot.send_message(user.id, purchase_success, parse_mode="HTML")
    
    # Отправляем уведомление админу о покупке
    admin_notification = f"""
🛒 <b>НОВАЯ ПОКУПКА!</b>

👤 <b>Покупатель:</b>
ID: {user.id}
Username: @{user.username}
Имя: {user.full_name}

🎮 <b>Аккаунт:</b> {name}
💰 <b>Цена:</b> {price}₃
🆔 <b>ID аккаунта:</b> {acc_id}
📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
    """
    
    await bot.send_message(ADMIN_ID, admin_notification, parse_mode="HTML")
    
    # Если указан канал, публикуем там
    if CHANNEL_ID:
        channel_post = f"""
✅ <b>Покупка совершена!</b>

🎮 Аккаунт: {name}
💰 Цена: {price}₽
⏰ Время: {datetime.now().strftime('%H:%M')}
        """
        await bot.send_message(CHANNEL_ID, channel_post, parse_mode="HTML")
    
    await callback.answer()

@dp.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    categories = get_categories()
    if not categories:
        await callback.message.edit_text("Категории пока пусты.")
        await callback.answer()
        return
    
    text = "📂 <b>Выберите категорию:</b>"
    await callback.message.edit_text(text, reply_markup=categories_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "back_to_accounts")
async def back_to_accounts(callback: CallbackQuery):
    # Здесь нужно сохранять category_id, но для простоты возвращаем к категориям
    text = "📂 <b>Выберите категорию:</b>"
    await callback.message.edit_text(text, reply_markup=categories_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: CallbackQuery):
    await callback.message.delete()
    await bot.send_message(callback.from_user.id, "Главное меню:", reply_markup=main_menu())
    await callback.answer()

# Функция для статистики
async def get_stats():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    
    # Общая статистика
    cursor.execute("SELECT COUNT(*) FROM categories")
    categories_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM accounts")
    accounts_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE quantity > 0")
    available_accounts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM purchases")
    purchases_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(price) FROM purchases")
    total_revenue = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM purchases")
    unique_buyers = cursor.fetchone()[0]
    
    conn.close()
    
    stats = f"""
📊 <b>Статистика магазина:</b>

📂 Категорий: {categories_count}
🎮 Аккаунтов всего: {accounts_count}
🟢 Доступно сейчас: {available_accounts}
🛒 Покупок всего: {purchases_count}
👥 Уникальных покупателей: {unique_buyers}
💰 Общая выручка: {total_revenue}₽
    """
    
    return stats

@dp.message()
async def handle_other_messages(message: types.Message):
    if message.text:
        await message.answer("Используйте кнопки меню для навигации.", reply_markup=main_menu())

# Запуск бота
async def main():
    init_db()  # Инициализируем базу данных
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
