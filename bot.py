# bot.py
import os
from flask import Flask, request
import telebot
from threading import Thread

app = Flask(__name__)
bot = telebot.TeleBot(os.environ['BOT_TOKEN'])

# Храним ID запущенного потока бота
bot_thread = None

def run_bot():
    """Запуск бота в отдельном потоке"""
    print("Бот запускается...")
    
    # Удаляем старые вебхуки
    bot.remove_webhook()
    
    # Получаем URL Railway
    railway_url = os.environ.get('RAILWAY_STATIC_URL', '')
    if railway_url:
        # Устанавливаем вебхук
        bot.set_webhook(url=f"{railway_url}/webhook")
        print(f"Вебхук установлен: {railway_url}/webhook")
    else:
        # Если URL нет, используем polling (для локальной разработки)
        print("Используем polling...")
        bot.polling(none_stop=True)

@app.route('/')
def home():
    return "🤖 Бот работает на Railway!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка вебхуков от Telegram"""
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return ''
    return ''

@app.route('/health')
def health():
    """Проверка работоспособности"""
    return 'OK', 200

# Команды бота
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "✅ Бот работает на Railway!")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, "Доступные команды: /start, /help")

if __name__ == '__main__':
    # Запускаем бот в отдельном потоке
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Запускаем Flask сервер
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
