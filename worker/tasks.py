import telebot, os, sys
from psycopg2 import Error, pool
from dotenv import load_dotenv
load_dotenv()
from .celery import app


bot = telebot.TeleBot(os.getenv("TOKEN_BOT"))

try:
    connection_pool = pool.SimpleConnectionPool(1, 2,
        database="postgres",
        user="postgres",
        password="postgres",
        host="postgres",
        port="5432",
    )

    # cursor = connection.cursor()
    print("Успешное подключение к БД!")
except (Exception, Error) as e:
    print("Не удалось подключиться к БД\nОшибка:", e)
    sys.exit()


@app.task
def create_table():
    try:
        connection = connection_pool.getconn()
        cursor = connection.cursor()
        cursor.execute("""create table users
                    (id serial primary key,
                    user_id bigserial);""")
        connection.commit()
        print("Таблица users успешно создана!")
    except (Exception, Error) as e:
        print("Не удалось создать таблицу users в БД\nВозможно она уже была создана ранее\nОшибка:", e)
    finally:
        cursor.close()
        connection_pool.putconn(connection)


@app.task
def send_signal(coin, movement):
    connection = connection_pool.getconn()
    cursor = connection.cursor()
    cursor.execute("select user_id from users;")

    users = cursor.fetchall()

    for user in users:
        bot.send_message(user[0], f"{movement}\n{coin}")

    cursor.close()
    connection_pool.putconn(connection)


@app.task
def is_check_user_id(user_id):
    try:
        connection = connection_pool.getconn()
        cursor = connection.cursor()
        cursor.execute(f"select * from users where user_id = {user_id};")
    except Error as e:
        bot.send_message(user_id, "Произошла ошибка!!!\nПожалуйста, попробуйте позже")
        print(f"Error select: {e}")
        return
    else:
        if len(cursor.fetchall()) > 0:
            bot.send_message(user_id, "Вы уже есть в базе данных\nМожете не беспокоиться)")
            return True
        return False
    finally:
        cursor.close()
        connection_pool.putconn(connection)


@app.task
def add_user_id(check, user_id):
    if check:
        return
    
    try:
        connection = connection_pool.getconn()
        cursor = connection.cursor()
        cursor.execute(f"insert into users (user_id) values ({user_id});")
        connection.commit()
    except Error as e:
        bot.send_message(user_id, "Ошибка на сервере!!! Не удалось добавить id вашего аккаунта в базу данных(\nПожалуйста, попробуйте позже")
        print("Не удалось добавить id аккаунта в БД(")
    else:
        bot.send_message(user_id, "Всё прошло успешно) Я запомнил вас. Ждите сигналов")
        print("id аккаунта добавлен в БД")
    finally:
        cursor.close()
        connection_pool.putconn(connection)