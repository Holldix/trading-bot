import telebot, os
from telebot.types import Message
from celery import chain
from dotenv import load_dotenv
load_dotenv()
from worker.tasks import is_check_user_id, add_user_id

bot = telebot.TeleBot(os.getenv("TOKEN_BOT"))


@bot.message_handler(commands=["start"])
def start(message: Message):
    bot.send_message(message.from_user.id, "Добавляю id вашего аккаунта в базу данных...\nПожалуйста, подождите!!!")

    chain(is_check_user_id.s(message.from_user.id), add_user_id.s(message.from_user.id)).apply_async()


bot.polling(none_stop=True, interval=0)
