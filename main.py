import telebot
from telebot import types

# Замените 'YOUR_BOT_TOKEN' на токен вашего бота
TOKEN = '8357573814:AAEzn5-67iylGo-U90YAIgFqgONyWfs97PE'
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я бот, который отвечает взаимно на приветствия. Просто напиши 'привет'!")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    # Проверяем, содержит ли сообщение "привет" (в любом регистре)
    if 'привет' in message.text.lower():
        bot.reply_to(message, "Привет!")
    else:
        bot.reply_to(message, "Напиши 'привет', и я отвечу взаимно!")

if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()