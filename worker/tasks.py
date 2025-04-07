importimport telebot
import os
import sys
import logging
import redis
from psycopg2 import Error, pool
from dotenv import load_dotenv
from .celery import app

load_dotenv()

bot = telebot.TeleBot(os.getenv("TOKEN_BOT"))
r_users = redis.Redis(host="redis", port=6379, db=2, decode_responses=True)

try:
    connection_pool = pool.SimpleConnectionPool(1, 2,
        database="postgres",
        user="postgres",
        password="postgres",
        host="postgres",
        port="5432",
    )
    print("Успешное подключение к БД!")
except (Exception, Error) as e:
    print("Не удалось подключиться к БД\nОшибка:", e)
    sys.exit()

@app.task(queue='high_priority', ignore_result=True)
def send_signal(coin, movement):
    try:
        cached_users = r_users.smembers("active_users")
        if cached_users:
            for user_id in cached_users:
                bot.send_message(user_id, f"{movement}\n{coin}")
            return

        connection = connection_pool.getconn()
        cursor = connection.cursor()
        cursor.execute("SELECT user_id FROM users;")
        users = cursor.fetchall()
        
        for user in users:
            user_id = str(user[0])
            bot.send_message(user_id, f"{movement}\n{coin}")
            r_users.sadd("active_users", user_id)
        
        r_users.expire("active_users", 3600)
    except Exception as e:
        logging.error(f"Ошибка отправки сигнала: {e}")
    finally:
        cursor.close()
        connection_pool.putconn(connection)

@app.task(ignore_result=True)
def create_table():
    try:
        connection = connection_pool.getconn()
        cursor = connection.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS users
                      (id serial primary key,
                      user_id bigserial);""")
        connection.commit()
        print("Таблица users готова!")
    except (Exception, Error) as e:
        print("Ошибка создания таблицы:", e)
    finally:
        cursor.close()
        connection_pool.putconn(connection)

@app.task(ignore_result=True)
def is_check_user_id(user_id):
    try:
        if r_users.get(f"user:{user_id}"):
            bot.send_message(user_id, "Вы уже есть в базе данных\nМожете не беспокоиться)")
            return True

        connection = connection_pool.getconn()
        cursor = connection.cursor()
        cursor.execute(f"SELECT * FROM users WHERE user_id = {user_id};")
        
        if len(cursor.fetchall()) > 0:
            r_users.setex(f"user:{user_id}", 3600, "1")
            bot.send_message(user_id, "Вы уже есть в базе данных\nМожете не беспокоиться)")
            return True
        return False
    except Error as e:
        bot.send_message(user_id, "Произошла ошибка!!!\nПожалуйста, попробуйте позже")
        print(f"Error select: {e}")
        return
    finally:
        cursor.close()
        connection_pool.putconn(connection)

@app.task(ignore_result=True)
def add_user_id(check, user_id):
    if check:
        return
    
    try:
        connection = connection_pool.getconn()
        cursor = connection.cursor()
        cursor.execute(f"INSERT INTO users (user_id) VALUES ({user_id});")
        connection.commit()
        r_users.setex(f"user:{user_id}", 3600, "1")
        r_users.sadd("active_users", user_id)
        bot.send_message(user_id, "Всё прошло успешно) Я запомнил вас. Ждите сигналов")
        print("id аккаунта добавлен в БД")
    except Error as e:
        bot.send_message(user_id, "Ошибка на сервере!!! Не удалось добавить id вашего аккаунта в базу данных(\nПожалуйста, попробуйте позже")
        print("Не удалось добавить id аккаунта в БД(")
    finally:
        cursor.close()
        connection_pool.putconn(connection)
