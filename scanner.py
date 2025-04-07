import os
import time
import requests
import redis
import logging
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from tradingview_ta import TA_Handler, Interval
from worker.tasks import send_signal, create_table

# Загрузка переменных окружения
load_dotenv()

API_KEY = os.getenv("API_KEY")
LOG_FILE = os.getenv("LOG_FILE", "log.txt")
PERCENT = float(os.getenv("PERCENT", 3))

INTERVAL_IN_MINUTE = 1
NUMBER_OF_COINS = 500
TIME_UPDATED_LIST_COINS = 60 * 60

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Redis
def init_redis(db):
    return redis.Redis(host="redis", port=6379, db=db, decode_responses=True)

r_coins = init_redis(0)
r_open = init_redis(1)
r_coins.flushdb()
r_open.flushdb()

# Получение монет
def get_list_coins():
    try:
        response = requests.get(
            "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
            headers={'X-CMC_PRO_API_KEY': API_KEY},
            params={"limit": NUMBER_OF_COINS}
        )
        response.raise_for_status()
        data = response.json()
        return [coin['symbol'] for coin in data.get('data', [])]
    except Exception as e:
        logging.error(f"Ошибка получения списка монет: {e}")
        return []

# Отправка webhook-уведомлений
def send_alert(message):
    if not ALERT_WEBHOOK:
        return
    try:
        requests.post(ALERT_WEBHOOK, json={"content": message})
    except Exception as e:
        logging.warning(f"Ошибка отправки webhook: {e}")

# Визуализация изменений
history = []

def plot_chart():
    if not history:
        return
    try:
        coins, values = zip(*history[-10:])
        plt.figure(figsize=(10, 4))
        colors = ["green" if v >= 0 else "red" for v in values]
        plt.bar(coins, values, color=colors)
        plt.title("ТОП 10 изменений за последние 10 минут")
        plt.ylabel("% Изменение")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig("top_changes.png")
        plt.close()
    except Exception as e:
        logging.warning(f"Ошибка построения графика: {e}")

# Основной сканер
def scanner(minute):
    logging.info(f"Минута {minute}")
    coins = r_coins.smembers("coins")
    if not coins:
        coins = get_list_coins()
        if not coins:
            logging.warning("Пустой список монет, пропуск...")
            return
        r_coins.sadd("coins", *coins)
        r_coins.expire("coins", TIME_UPDATED_LIST_COINS)
        logging.info("Список монет обновлён.")

    max_change = 0
    top_coin = ""

    for coin in coins:
        handler = TA_Handler(
            screener="crypto",
            exchange="BINANCE",
            symbol=f"{coin}USDT",
            interval=Interval.INTERVAL_1_MINUTE,
        )

        try:
            indicators = handler.get_analysis().indicators
            open_price = float(indicators["open"])
            close_price = float(indicators["close"])
            rsi = indicators.get("RSI", None)
            volume = indicators.get("volume", None)
            macd = indicators.get("MACD.macd", None)
            signal = indicators.get("MACD.signal", None)

        except Exception:
            continue

        r_open.lpush(f"{coin}:history", open_price)
        r_open.ltrim(f"{coin}:history", 0, 9)  # хранить только 10 последних
        open_stored = float(r_open.lindex(f"{coin}:history", 0) or open_price)
        change = (close_price - open_stored) / open_stored * 100

        # PUMP/DUMP логика
        if change >= PERCENT:
            msg = f"🟢 {coin} PUMP +{change:.2f}%"
            logging.info(msg)
            send_signal.delay(coin, msg)
            send_alert(msg)
            r_open.delete(f"{coin}:history")

        elif change <= -PERCENT:
            msg = f"🔴 {coin} DUMP {change:.2f}%"
            logging.info(msg)
            send_signal.delay(coin, msg)
            send_alert(msg)
            r_open.delete(f"{coin}:history")
            logging.info(f"{coin} | Change: {change:.2f}% | RSI: {rsi} | Volume: {volume} | MACD: {macd} | Signal: {signal}")


        if abs(change) > max_change:
            max_change = abs(change)
            top_coin = coin

    if top_coin:
        history.append((top_coin, max_change))
        plot_chart()
        logging.info(f"MAX CHANGE: {top_coin} {max_change:.2f}%")

# Создание таблицы и старт
create_table.delay()

minute = 0
while True:
    start = time.time()
    minute += 1
    scanner(minute)
    time.sleep(max(0, 60 - (time.time() - start)))

