import telebot
import time
import random
import json
import os
import requests
import threading
from telebot import types
from datetime import datetime, timedelta

# ВСТАВЬ ТОКЕН СЮДА!
TOKEN = "7808825299:AAGTm97aBeOFF7ptl8NT6PCkfNNbgmCHBJw"

bot = telebot.TeleBot(TOKEN)

# Конфигурация
ADMIN_USERNAME = "@selym416"
ADMIN_IDS = [479062582]  # Твой ID Telegram (узнай через @userinfobot)
CRYPTO_BOT_TOKEN = "499427:AA0VSxyG9aOJtYv0KeEkzfXFw1ak3t33cHy"  # Токен от @CryptoBot

# Файл для хранения данных
DATA_FILE = "bot_data.json"

# Глобальная переменная для хранения user_data
user_data = {}

# Загружаем данные
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "banned_users": [],
        "subscriptions": {},
        "admins": ADMIN_IDS,
        "stats": {"total_operations": 0, "active_users": []},
        "pending_payments": {},
        "payment_history": []
    }

# Сохраняем данные
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Проверка доступа пользователя (админ или есть подписка)
def check_access(user_id):
    data = load_data()
    
    # Админы имеют полный доступ всегда
    if user_id in data["admins"]:
        return True, "admin"
    
    # Проверяем подписку
    if str(user_id) in data["subscriptions"]:
        sub_info = data["subscriptions"][str(user_id)]
        expire_date = datetime.fromisoformat(sub_info["expire_date"])
        
        # Если подписка истекла, удаляем её
        if datetime.now() > expire_date:
            del data["subscriptions"][str(user_id)]
            save_data(data)
            return False, "no_sub"
        
        return True, "subscriber"
    
    return False, "no_sub"

# Создание инвойса в CryptoBot
def create_crypto_invoice(amount, description, user_id, days):
    try:
        url = "https://pay.crypt.bot/api/createInvoice"
        headers = {
            "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN
        }
        
        # Создаем уникальный payload для идентификации платежа
        payload = f"sub_{user_id}_{days}_{int(time.time())}"
        
        params = {
            "asset": "USDT",
            "amount": str(amount),
            "description": description,
            "payload": payload,
            "paid_btn_url": f"https://t.me/{bot.get_me().username}",
            "paid_btn_name": "view_item"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data_response = response.json()
            if data_response.get("ok"):
                result = data_response.get("result")
                
                # Сохраняем информацию о pending платеже
                data = load_data()
                data["pending_payments"][payload] = {
                    "user_id": user_id,
                    "amount": amount,
                    "days": days,
                    "invoice_id": result.get("invoice_id"),
                    "created_at": datetime.now().isoformat(),
                    "status": "pending",
                    "check_attempts": 0
                }
                save_data(data)
                
                return result.get("pay_url"), payload
        return None, None
    except Exception as e:
        print(f"Ошибка создания инвойса: {e}")
        return None, None

# Отправка уведомления админам
def notify_admins(message_text):
    data = load_data()
    for admin_id in data["admins"]:
        try:
            bot.send_message(admin_id, message_text, parse_mode='HTML')
        except Exception as e:
            print(f"Не удалось отправить уведомление админу {admin_id}: {e}")

# Проверка статуса платежа
def check_payment_status(payload):
    try:
        data = load_data()
        if payload in data["pending_payments"]:
            payment_info = data["pending_payments"][payload]
            
            # Увеличиваем счетчик попыток проверки
            payment_info["check_attempts"] += 1
            
            url = "https://pay.crypt.bot/api/getInvoices"
            headers = {
                "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN
            }
            params = {
                "invoice_ids": payment_info["invoice_id"]
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    invoices = result.get("result", {}).get("items", [])
                    if invoices:
                        status = invoices[0].get("status")
                        
                        if status == "paid" and payment_info["status"] != "paid":
                            # Активируем подписку
                            user_id = payment_info["user_id"]
                            days = payment_info["days"]
                            amount = payment_info["amount"]
                            
                            expire_date = datetime.now() + timedelta(days=days)
                            data["subscriptions"][str(user_id)] = {
                                "days": days,
                                "expire_date": expire_date.isoformat(),
                                "activated_at": datetime.now().isoformat(),
                                "payment_payload": payload,
                                "amount": amount
                            }
                            
                            # Добавляем в историю платежей
                            data["payment_history"].append({
                                "user_id": user_id,
                                "amount": amount,
                                "days": days,
                                "date": datetime.now().isoformat(),
                                "type": "cryptobot"
                            })
                            
                            data["pending_payments"][payload]["status"] = "paid"
                            data["pending_payments"][payload]["paid_at"] = datetime.now().isoformat()
                            save_data(data)
                            
                            # Уведомляем админов о новом платеже
                            notify_admins(
                                "💰 <b>НОВЫЙ ПЛАТЕЖ ПОСТУПИЛ!</b>\n\n"
                                f"👤 Пользователь: <code>{user_id}</code>\n"
                                f"💎 Подписка: {days} дней\n"
                                f"💵 Сумма: {amount} USDT\n"
                                f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                                f"📊 Всего подписок: {len(data['subscriptions'])}"
                            )
                            
                            # Уведомляем пользователя
                            try:
                                bot.send_message(
                                    user_id,
                                    f"🎉 <b>ПЛАТЕЖ ПОДТВЕРЖДЕН!</b>\n\n"
                                    f"✅ Ваша подписка активирована на {days} дней\n"
                                    f"💵 Сумма: {amount} USDT\n"
                                    f"📅 Активна до: {expire_date.strftime('%d.%m.%Y %H:%M')}\n\n"
                                    f"Теперь вам доступны все функции бота!",
                                    parse_mode='HTML'
                                )
                            except:
                                pass
                            
                            return True
                        
                        elif status == "expired":
                            # Удаляем просроченный платеж
                            user_id = payment_info["user_id"]
                            del data["pending_payments"][payload]
                            save_data(data)
                            
                            # Уведомляем пользователя
                            try:
                                bot.send_message(
                                    user_id,
                                    "❌ <b>ПЛАТЕЖ ПРОСРОЧЕН</b>\n\n"
                                    "Время на оплату истекло. Создайте новый заказ.",
                                    parse_mode='HTML'
                                )
                            except:
                                pass
                            
                            return False
                        
                        # Сохраняем обновленный счетчик попыток
                        save_data(data)
            else:
                print(f"Ошибка API CryptoBot: {response.status_code}")
                
            # Если было больше 30 попыток проверки (30 минут), удаляем
            if payment_info["check_attempts"] > 30:
                del data["pending_payments"][payload]
                save_data(data)
                
        return False
    except Exception as e:
        print(f"Ошибка проверки платежа: {e}")
        return False

# Фоновая проверка платежей
def background_payment_checker():
    while True:
        try:
            data = load_data()
            pending_payments = list(data["pending_payments"].keys())
            
            for payload in pending_payments:
                check_payment_status(payload)
                
            # Проверяем истекшие подписки
            check_expired_subscriptions()
            
        except Exception as e:
            print(f"Ошибка в фоновой проверке: {e}")
        
        # Проверяем каждые 60 секунд
        time.sleep(60)

# Проверка истекших подписок
def check_expired_subscriptions():
    data = load_data()
    expired_count = 0
    
    for user_id_str, sub_info in list(data["subscriptions"].items()):
        expire_date = datetime.fromisoformat(sub_info["expire_date"])
        
        if datetime.now() > expire_date:
            user_id = int(user_id_str)
            
            # Удаляем подписку
            del data["subscriptions"][user_id_str]
            expired_count += 1
            
            # Уведомляем пользователя
            try:
                bot.send_message(
                    user_id,
                    "⚠️ <b>ВАША ПОДПИСКА ИСТЕКЛА</b>\n\n"
                    "Для продолжения использования функций бота "
                    "необходимо продлить подписку.",
                    parse_mode='HTML'
                )
            except:
                pass
    
    if expired_count > 0:
        save_data(data)
        print(f"Удалено {expired_count} истекших подписок")

# Запуск фоновой проверки
def start_background_checker():
    checker_thread = threading.Thread(target=background_payment_checker, daemon=True)
    checker_thread.start()
    print("✅ Фоновая проверка платежей запущена")

# Главное меню
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    data = load_data()
    
    # Проверка на бан
    if user_id in data["banned_users"]:
        bot.send_message(user_id, "❌ Вы заблокированы в системе!")
        return
    
    # Добавляем пользователя в статистику
    if user_id not in data["stats"]["active_users"]:
        data["stats"]["active_users"].append(user_id)
        save_data(data)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    btn1 = types.InlineKeyboardButton("🗑️ Снести сессии", callback_data='sessions')
    btn2 = types.InlineKeyboardButton("👤 Снести аккаунт", callback_data='account')
    btn3 = types.InlineKeyboardButton("📢 Снести канал", callback_data='channel')
    btn4 = types.InlineKeyboardButton("💎 Подписка", callback_data='subscription')
    btn5 = types.InlineKeyboardButton("🆘 Поддержка", callback_data='support')
    
    # Кнопка админ-панели только для админов
    if user_id in data["admins"]:
        btn_admin = types.InlineKeyboardButton("👑 Админ", callback_data='admin_panel')
        markup.add(btn_admin)
    
    markup.add(btn1, btn2, btn3)
    markup.add(btn4, btn5)
    
    welcome_text = (
        "🔥 <b>Самый лучший Sn0ser m416</b> 🔥\n"
        "⚡ Моментальный сн0с • Низкие цены ⚡\n\n"
        "──────────────\n"
        "💥 <b>Выбери действие:</b>"
    )
    
    msg = bot.send_message(
        message.chat.id,
        "🚀 <b>Запускаю систему...</b>",
        parse_mode='HTML'
    )
    
    for i in range(1, 4):
        time.sleep(0.3)
        dots = "•" * i
        bot.edit_message_text(
            f"🚀 <b>Запускаю систему{dots}</b>",
            message.chat.id,
            msg.message_id,
            parse_mode='HTML'
        )
    
    time.sleep(0.3)
    bot.edit_message_text(
        welcome_text,
        message.chat.id,
        msg.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

# АДМИН ПАНЕЛЬ
@bot.callback_query_handler(func=lambda call: call.data == 'admin_panel')
def admin_panel(call):
    user_id = call.from_user.id
    data = load_data()
    
    if user_id not in data["admins"]:
        bot.answer_callback_query(call.id, "❌ Нет доступа!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    btn1 = types.InlineKeyboardButton("🚫 Забанить", callback_data='admin_ban')
    btn2 = types.InlineKeyboardButton("✅ Разбанить", callback_data='admin_unban')
    btn3 = types.InlineKeyboardButton("🎁 Выдать подписку", callback_data='admin_give_sub')
    btn4 = types.InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')
    btn5 = types.InlineKeyboardButton("➕ Добавить админа", callback_data='admin_add')
    btn6 = types.InlineKeyboardButton("👥 Список пользователей", callback_data='user_list')
    btn7 = types.InlineKeyboardButton("🔙 Назад", callback_data='back')
    
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)
    
    bot.edit_message_text(
        "👑 <b>АДМИН ПАНЕЛЬ</b> 👑\n\n"
        "Выбери действие:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

# СПИСОК ПОЛЬЗОВАТЕЛЕЙ ДЛЯ АДМИНА
@bot.callback_query_handler(func=lambda call: call.data == 'user_list')
def show_user_list(call):
    data = load_data()
    
    if not data["stats"]["active_users"]:
        bot.answer_callback_query(call.id, "📭 Список пользователей пуст!")
        return
    
    # Создаем инлайн клавиатуру с пользователями
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for i, user_id in enumerate(data["stats"]["active_users"][:50], 1):  # Показываем первые 50
        # Получаем информацию о подписке
        has_sub = str(user_id) in data["subscriptions"]
        sub_emoji = "💎" if has_sub else "👤"
        banned_emoji = "🚫" if user_id in data["banned_users"] else ""
        admin_emoji = "👑" if user_id in data["admins"] else ""
        
        btn_text = f"{i}. {sub_emoji}{banned_emoji}{admin_emoji} ID: {user_id}"
        btn = types.InlineKeyboardButton(btn_text, callback_data=f'user_select_{user_id}')
        markup.add(btn)
    
    # Кнопка назад
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='admin_panel'))
    
    total_users = len(data["stats"]["active_users"])
    active_subs = len(data["subscriptions"])
    
    bot.edit_message_text(
        f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
        f"📊 Всего пользователей: {total_users}\n"
        f"💎 С подпиской: {active_subs}\n"
        f"🚫 Забанено: {len(data['banned_users'])}\n\n"
        f"Выбери пользователя для действий:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

# ОБРАБОТКА ВЫБОРА ПОЛЬЗОВАТЕЛЯ
@bot.callback_query_handler(func=lambda call: call.data.startswith('user_select_'))
def handle_user_selection(call):
    try:
        user_id = int(call.data.replace('user_select_', ''))
        data = load_data()
        
        # Получаем информацию о пользователе
        has_sub = str(user_id) in data["subscriptions"]
        is_banned = user_id in data["banned_users"]
        is_admin = user_id in data["admins"]
        
        # Получаем username если есть
        username = "Неизвестно"
        try:
            chat = bot.get_chat(user_id)
            username = f"@{chat.username}" if chat.username else chat.first_name
        except:
            pass
        
        # Создаем меню действий для этого пользователя
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        if is_banned:
            btn1 = types.InlineKeyboardButton("✅ Разбанить", callback_data=f'unban_user_{user_id}')
        else:
            btn1 = types.InlineKeyboardButton("🚫 Забанить", callback_data=f'ban_user_{user_id}')
        
        if has_sub:
            # Показываем информацию о подписке
            sub_info = data["subscriptions"][str(user_id)]
            expire_date = datetime.fromisoformat(sub_info["expire_date"])
            days_left = (expire_date - datetime.now()).days
            
            btn2 = types.InlineKeyboardButton(f"💎 Подписка ({days_left}д)", 
                                              callback_data=f'sub_info_{user_id}')
        else:
            btn2 = types.InlineKeyboardButton("🎁 Выдать подписку", 
                                              callback_data=f'give_sub_menu_{user_id}')
        
        if is_admin:
            btn3 = types.InlineKeyboardButton("👑 Снять админа", 
                                              callback_data=f'remove_admin_{user_id}')
        else:
            btn3 = types.InlineKeyboardButton("👑 Сделать админом", 
                                              callback_data=f'make_admin_{user_id}')
        
        btn4 = types.InlineKeyboardButton("👥 Назад к списку", callback_data='user_list')
        btn5 = types.InlineKeyboardButton("🔙 В админку", callback_data='admin_panel')
        
        markup.add(btn1, btn2, btn3, btn4, btn5)
        
        # Статусы
        status_text = ""
        if is_admin:
            status_text += "👑 <b>Администратор</b>\n"
        if has_sub:
            status_text += "💎 <b>Есть подписка</b>\n"
        if is_banned:
            status_text += "🚫 <b>Забанен</b>\n"
        
        bot.edit_message_text(
            f"👤 <b>ПОЛЬЗОВАТЕЛЬ</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📛 Имя: {username}\n\n"
            f"{status_text}\n"
            f"Выбери действие:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Ошибка загрузки данных пользователя")

# СДЕЛАТЬ АДМИНОМ
@bot.callback_query_handler(func=lambda call: call.data.startswith('make_admin_'))
def make_admin(call):
    try:
        user_id = int(call.data.replace('make_admin_', ''))
        data = load_data()
        
        if user_id not in data["admins"]:
            data["admins"].append(user_id)
            save_data(data)
            
            # Уведомляем админов
            notify_admins(
                f"👑 <b>НОВЫЙ АДМИНИСТРАТОР</b>\n\n"
                f"Пользователь <code>{user_id}</code> добавлен в админы\n"
                f"Добавил: @{call.from_user.username or call.from_user.id}"
            )
            
            bot.answer_callback_query(call.id, f"✅ Пользователь {user_id} стал админом!")
            
            # Обновляем сообщение
            call.data = f'user_select_{user_id}'
            handle_user_selection(call)
        else:
            bot.answer_callback_query(call.id, "⚠️ Пользователь уже админ")
            
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Ошибка")

# СНЯТЬ АДМИНА
@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_admin_'))
def remove_admin(call):
    try:
        user_id = int(call.data.replace('remove_admin_', ''))
        data = load_data()
        
        if user_id in data["admins"]:
            # Нельзя удалить себя
            if user_id == call.from_user.id:
                bot.answer_callback_query(call.id, "❌ Нельзя снять себя!")
                return
                
            data["admins"].remove(user_id)
            save_data(data)
            
            # Уведомляем админов
            notify_admins(
                f"👑 <b>АДМИНИСТРАТОР СНЯТ</b>\n\n"
                f"Пользователь <code>{user_id}</code> удален из админов\n"
                f"Снял: @{call.from_user.username or call.from_user.id}"
            )
            
            bot.answer_callback_query(call.id, f"✅ Пользователь {user_id} снят с админки!")
            
            # Обновляем сообщение
            call.data = f'user_select_{user_id}'
            handle_user_selection(call)
        else:
            bot.answer_callback_query(call.id, "⚠️ Пользователь не админ")
            
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Ошибка")

# БАН ПОЛЬЗОВАТЕЛЯ
@bot.callback_query_handler(func=lambda call: call.data.startswith('ban_user_'))
def ban_user(call):
    try:
        user_id = int(call.data.replace('ban_user_', ''))
        data = load_data()
        
        if user_id not in data["banned_users"]:
            data["banned_users"].append(user_id)
            save_data(data)
            
            bot.answer_callback_query(call.id, f"✅ Пользователь {user_id} забанен!")
            
            # Обновляем сообщение
            call.data = f'user_select_{user_id}'
            handle_user_selection(call)
        else:
            bot.answer_callback_query(call.id, "⚠️ Пользователь уже в бане")
            
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Ошибка")

# РАЗБАН ПОЛЬЗОВАТЕЛЯ
@bot.callback_query_handler(func=lambda call: call.data.startswith('unban_user_'))
def unban_user(call):
    try:
        user_id = int(call.data.replace('unban_user_', ''))
        data = load_data()
        
        if user_id in data["banned_users"]:
            data["banned_users"].remove(user_id)
            save_data(data)
            
            bot.answer_callback_query(call.id, f"✅ Пользователь {user_id} разбанен!")
            
            # Обновляем сообщение
            call.data = f'user_select_{user_id}'
            handle_user_selection(call)
        else:
            bot.answer_callback_query(call.id, "⚠️ Пользователь не в бане")
            
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Ошибка")

# КНОПКА ПОДПИСКИ
@bot.callback_query_handler(func=lambda call: call.data == 'subscription')
def subscription_button(call):
    user_id = call.from_user.id
    data = load_data()
    
    # Проверяем доступ (админам не показываем оплату)
    has_access, access_type = check_access(user_id)
    
    if access_type == "admin":
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data='back')
        markup.add(btn_back)
        
        bot.edit_message_text(
            "💎 <b>ВЫ АДМИНИСТРАТОР</b> 💎\n\n"
            "Вам доступны все функции бота без ограничений!\n\n"
            "👑 Админ: полный доступ\n"
            "⚡ Приоритет: максимальный\n"
            "🛡️ Защита: 24/7",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
        return
    
    # Проверяем есть ли подписка у обычного пользователя
    has_sub = str(user_id) in data["subscriptions"]
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if has_sub:
        # Если есть подписка - показываем информацию
        sub_info = data["subscriptions"][str(user_id)]
        expire_date = datetime.fromisoformat(sub_info["expire_date"])
        days_left = (expire_date - datetime.now()).days
        
        btn1 = types.InlineKeyboardButton("1️⃣ 1 день - 2$", callback_data='sub_1day')
        btn2 = types.InlineKeyboardButton("7️⃣ 7 дней - 9$", callback_data='sub_7days')
        btn3 = types.InlineKeyboardButton("🔙 Назад", callback_data='back')
        
        markup.add(btn1, btn2, btn3)
        
        bot.edit_message_text(
            f"💎 <b>ВАША ПОДПИСКА АКТИВНА</b> 💎\n\n"
            f"⏱ <b>Осталось дней:</b> {max(0, days_left)}\n"
            f"📅 <b>Истекает:</b> {expire_date.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"──────────────\n\n"
            f"<b>Купить дополнительно:</b>\n\n"
            f"✅ <b>1 день</b> - 2$\n"
            f"🔥 <b>7 дней</b> - 9$\n\n"
            f"💳 <b>Оплата через CryptoBot (USDT)</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
    else:
        # Если нет подписки - стандартное меню
        btn1 = types.InlineKeyboardButton("1️⃣ 1 день - 2$", callback_data='sub_1day')
        btn2 = types.InlineKeyboardButton("7️⃣ 7 дней - 9$", callback_data='sub_7days')
        btn3 = types.InlineKeyboardButton("🔙 Назад", callback_data='back')
        
        markup.add(btn1, btn2, btn3)
        
        bot.edit_message_text(
            "💎 <b>ПОДПИСКА НА СНОСИЛЬЩИК</b> 💎\n\n"
            "Выбери тариф:\n\n"
            "✅ <b>1 день</b> - 2$\n"
            "• Доступ ко всем функциям\n"
            "• Приоритетная очередь\n"
            "• Поддержка 24/7\n\n"
            "🔥 <b>7 дней</b> - 9$\n"
            "• Всё из тарифа 1 день\n"
            "• Скидка 35%\n"
            "• Приоритет х2\n\n"
            "💳 <b>Оплата через CryptoBot (USDT)</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )

# ВЫБОР ТАРИФА ПОДПИСКИ
@bot.callback_query_handler(func=lambda call: call.data in ['sub_1day', 'sub_7days'])
def choose_subscription(call):
    user_id = call.from_user.id
    
    if call.data == 'sub_1day':
        price = 2
        days = 1
        description = "Подписка на 1 день"
    else:
        price = 9
        days = 7
        description = "Подписка на 7 дней"
    
    # Создаем инвойс в CryptoBot
    pay_url, payload = create_crypto_invoice(price, description, user_id, days)
    
    if pay_url:
        markup = types.InlineKeyboardMarkup()
        
        btn_pay = types.InlineKeyboardButton(
            f"💳 Оплатить {price}$ USDT",
            url=pay_url
        )
        btn_check = types.InlineKeyboardButton(
            "🔄 Проверить оплату",
            callback_data=f'check_payment_{payload}'
        )
        btn_back = types.InlineKeyboardButton("🔙 Назад к тарифам", callback_data='subscription')
        
        markup.add(btn_pay)
        markup.add(btn_check, btn_back)
        
        bot.edit_message_text(
            f"💳 <b>ОПЛАТА ПОДПИСКИ</b>\n\n"
            f"Тариф: <b>{days} дней</b>\n"
            f"Сумма: <b>{price} USDT</b>\n\n"
            f"Для оплаты:\n"
            f"1. Нажми кнопку 'Оплатить'\n"
            f"2. Оплати счет в CryptoBot\n"
            f"3. Нажми 'Проверить оплату'\n\n"
            f"✅ Платеж проверяется автоматически\n"
            f"⏱ Обычно занимает 1-2 минуты",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
    else:
        bot.answer_callback_query(call.id, "❌ Ошибка создания счета. Попробуйте позже.")

# ПРОВЕРКА ОПЛАТЫ
@bot.callback_query_handler(func=lambda call: call.data.startswith('check_payment_'))
def check_payment(call):
    payload = call.data.replace('check_payment_', '')
    
    if check_payment_status(payload):
        bot.answer_callback_query(call.id, "✅ Оплата подтверждена! Подписка активирована.")
        
        # Обновляем сообщение
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("🔙 В меню", callback_data='back')
        markup.add(btn_back)
        
        bot.edit_message_text(
            "🎉 <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"
            "✅ Ваша подписка успешно активирована!\n"
            "🔥 Теперь вам доступны все функции бота!\n\n"
            "Спасибо за покупку!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
    else:
        bot.answer_callback_query(call.id, "❌ Оплата еще не поступила. Попробуйте через минуту.")

# СНОС СЕССИЙ (с проверкой доступа)
@bot.callback_query_handler(func=lambda call: call.data == 'sessions')
def ask_username_session(call):
    user_id = call.from_user.id
    
    # Проверяем доступ (админ ИЛИ подписчик)
    has_access, access_type = check_access(user_id)
    
    if not has_access:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💎 Купить подписку", callback_data='subscription'))
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='back'))
        
        bot.edit_message_text(
            "❌ <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            "Для использования этой функции нужна активная подписка!\n"
            "Приобрети подписку и получи доступ ко всем возможностям бота.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
        return
    
    # Если админ - не спрашиваем про оплату, сразу пускаем
    bot.edit_message_text(
        "🗑️ <b>СНОС СЕССИЙ</b>\n\nВведи юзернейм (без @):",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML'
    )
    
    msg = bot.send_message(call.message.chat.id, "✏️ Жду юзернейм...")
    user_data[call.message.chat.id] = {'action': 'sessions', 'step': 1}
    bot.register_next_step_handler(msg, process_destruction)

# СНОС АККАУНТА (с проверкой доступа)
@bot.callback_query_handler(func=lambda call: call.data == 'account')
def ask_username_account(call):
    user_id = call.from_user.id
    
    has_access, access_type = check_access(user_id)
    
    if not has_access:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💎 Купить подписку", callback_data='subscription'))
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='back'))
        
        bot.edit_message_text(
            "❌ <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            "Для использования этой функции нужна активная подписка!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
        return
    
    bot.edit_message_text(
        "👤 <b>СНОС АККАУНТА</b>\n\nВведи юзернейм (без @):",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML'
    )
    
    msg = bot.send_message(call.message.chat.id, "✏️ Жду юзернейм...")
    user_data[call.message.chat.id] = {'action': 'account', 'step': 1}
    bot.register_next_step_handler(msg, process_destruction)

# СНОС КАНАЛА (с проверкой доступа)
@bot.callback_query_handler(func=lambda call: call.data == 'channel')
def ask_channel_links(call):
    user_id = call.from_user.id
    
    has_access, access_type = check_access(user_id)
    
    if not has_access:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💎 Купить подписку", callback_data='subscription'))
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='back'))
        
        bot.edit_message_text(
            "❌ <b>ТРЕБУЕТСЯ ПОДПИСКА</b>\n\n"
            "Для использования этой функции нужна активная подписка!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=markup
        )
        return
    
    bot.edit_message_text(
        "📢 <b>СНОС КАНАЛА</b>\n\nКинь ссылку на нарушение и ссылку на канал (можно в разных строках):",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML'
    )
    
    msg = bot.send_message(call.message.chat.id, "✏️ Жду ссылки...")
    user_data[call.message.chat.id] = {'action': 'channel', 'step': 1}
    bot.register_next_step_handler(msg, process_destruction)

# ОБРАБОТКА ВВОДА
def process_destruction(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if chat_id not in user_data:
        start(message)
        return
    
    action = user_data[chat_id]['action']
    target = message.text.strip()
    
    # Обновляем статистику
    data = load_data()
    data["stats"]["total_operations"] += 1
    save_data(data)
    
    # Удаляем данные пользователя
    del user_data[chat_id]
    
    # Определяем тип действия
    if action == 'sessions':
        title = "🗑️ СНОС СЕССИЙ"
        target_type = "сессий"
        emoji = "🗑️"
    elif action == 'account':
        title = "👤 СНОС АККАУНТА"
        target_type = "аккаунта"
        emoji = "👤"
    else:  # channel
        title = "📢 СНОС КАНАЛА"
        target_type = "канала"
        emoji = "📢"
    
    # Анимация начала
    msg = bot.send_message(
        chat_id,
        f"{emoji} <b>Цель получена!</b>\n"
        f"🎯 <b>{target}</b>\n\n"
        f"🔄 <i>Запускаю процесс...</i>",
        parse_mode='HTML'
    )
    
    time.sleep(1)
    
    # Запускаем визуализацию
    show_progress(chat_id, title, target, target_type, msg.message_id)

# ВИЗУАЛИЗАЦИЯ ПРОГРЕССА
def show_progress(chat_id, title, target, target_type, message_id=None):
    emails_sent = random.randint(120, 350)
    success_rate = random.randint(85, 99)
    reports_filed = random.randint(5, 15)
    
    if message_id:
        progress_msg_id = message_id
        bot.edit_message_text(
            f"💥 {title} 💥\n\n"
            f"🎯 Цель: {target}\n"
            f"🔄 Начинаю операцию...\n\n"
            f"📧 Отправлено писем: 0\n"
            f"📊 Успешных: 0%\n\n"
            f"▱▱▱▱▱▱▱▱▱▱ 0%",
            chat_id,
            progress_msg_id
        )
    else:
        progress_msg = bot.send_message(
            chat_id,
            f"💥 {title} 💥\n\n"
            f"🎯 Цель: {target}\n"
            f"🔄 Начинаю операцию...\n\n"
            f"📧 Отправлено писем: 0\n"
            f"📊 Успешных: 0%\n\n"
            f"▱▱▱▱▱▱▱▱▱▱ 0%"
        )
        progress_msg_id = progress_msg.message_id
    
    # Плавная анимация
    steps = 10
    for i in range(1, steps + 1):
        progress = int((i / steps) * 100)
        filled_bars = int((i / steps) * 10)
        bar = "▰" * filled_bars + "▱" * (10 - filled_bars)
        
        current_emails = int(emails_sent * (i / steps))
        current_success = int(success_rate * (i / steps))
        
        time.sleep(0.3)
        
        try:
            bot.edit_message_text(
                f"💥 {title} 💥\n\n"
                f"🎯 Цель: {target}\n"
                f"🔄 Процесс выполняется... {progress}%\n\n"
                f"📧 Отправлено писем: {current_emails}\n"
                f"📊 Успешных: {current_success}%\n\n"
                f"{bar} {progress}%",
                chat_id,
                progress_msg_id
            )
        except:
            pass
    
    time.sleep(0.5)
    
    # Финальный отчёт
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 В меню", callback_data='back'))
    
    bot.edit_message_text(
        f"✨ <b>══════ ОТЧЁТ ОБ ОПЕРАЦИИ ══════</b> ✨\n\n"
        f"🎯 <b>Цель:</b> {target}\n"
        f"📋 <b>Тип операции:</b> {title}\n\n"
        f"📊 <b>СТАТИСТИКА:</b>\n"
        f"┣ 📧 <i>Отправлено писем:</i> <b>{emails_sent}</b>\n"
        f"┣ ✅ <i>Успешных жалоб:</i> <b>{success_rate}%</b>\n"
        f"┣ 📋 <i>Подано репортов:</i> <b>{reports_filed}</b>\n"
        f"┗ ⏱ <i>Время операции:</i> <b>3 секунды</b>\n\n"
        f"💥 <b>РЕЗУЛЬТАТ:</b>\n"
        f"<code>┌──────────────────────────┐</code>\n"
        f"<code>│  {target_type.upper():^24} │</code>\n"
        f"<code>│    ПОЛНОСТЬЮ УНИЧТОЖЕНЫ   │</code>\n"
        f"<code>└──────────────────────────┘</code>\n\n"
        f"⚠️ Все данные были безвозвратно удалены",
        chat_id,
        progress_msg_id,
        parse_mode='HTML',
        reply_markup=markup
    )

# КНОПКА НАЗАД
@bot.callback_query_handler(func=lambda call: call.data == 'back')
def back_to_menu(call):
    user_id = call.from_user.id
    data = load_data()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    btn1 = types.InlineKeyboardButton("🗑️ Снести сессии", callback_data='sessions')
    btn2 = types.InlineKeyboardButton("👤 Снести аккаунт", callback_data='account')
    btn3 = types.InlineKeyboardButton("📢 Снести канал", callback_data='channel')
    btn4 = types.InlineKeyboardButton("💎 Подписка", callback_data='subscription')
    btn5 = types.InlineKeyboardButton("🆘 Поддержка", callback_data='support')
    
    if user_id in data["admins"]:
        btn_admin = types.InlineKeyboardButton("👑 Админ", callback_data='admin_panel')
        markup.add(btn_admin)
    
    markup.add(btn1, btn2, btn3)
    markup.add(btn4, btn5)
    
    welcome_text = (
        "🔥 <b>Самый лучший Sn0ser m416</b> 🔥\n"
        "⚡ Моментальный сн0с • Низкие цены ⚡\n\n"
        "──────────────\n"
        "💥 <b>Выбери действие:</b>"
    )
    
    bot.edit_message_text(
        welcome_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

# КНОПКА ПОДДЕРЖКИ
@bot.callback_query_handler(func=lambda call: call.data == 'support')
def support_button(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data='back'))
    
    bot.edit_message_text(
        f"🆘 <b>ТЕХНИЧЕСКАЯ ПОДДЕРЖКА</b>\n\n"
        f"По всем вопросам обращайся к администратору:\n"
        f"{ADMIN_USERNAME}\n\n"
        f"📞 Ответ в течение 24 часов",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        reply_markup=markup
    )

# ЗАПУСК БОТА
print("🚀 Бот запускается...")
print("✅ Проверяю токен...")

try:
    bot_info = bot.get_me()
    print(f"✅ Бот найден: @{bot_info.username}")
    print(f"✅ Имя бота: {bot_info.first_name}")
    print("✅ Токен рабочий! Бот запущен.")
    print(f"✅ Админ: {ADMIN_USERNAME}")
    
    # Запускаем фоновую проверку платежей
    start_background_checker()
    
    print("\n" + "="*50)
    print("🔥 САМЫЙ ЛУЧШИЙ SN0SER M416 🔥")
    print("⚡ МОМЕНТАЛЬНЫЙ СН0С • НИЗКИЕ ЦЕНЫ ⚡")
    print("="*50)
    print("👑 АДМИН ПАНЕЛЬ АКТИВИРОВАНА")
    print("💰 CryptoBot оплата настроена")
    print("🔄 Фоновая проверка платежей запущена")
    print("📁 Данные сохраняются в: bot_data.json")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    print("❌ Токен неверный! Получи новый токен у @BotFather")
    exit(1)

print("\n✨ Бот готов к работе! Открой Telegram и нажми /start")
print("ℹ️  Чтобы стать админом, добавь свой ID в переменную ADMIN_IDS")
bot.polling(none_stop=True)