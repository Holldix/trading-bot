import os
import time
import asyncio
import aiohttp
import redis
import logging
import matplotlib.pyplot as plt
from threading import Thread
from tradingview_ta import TA_Handler, Interval
from dotenv import load_dotenv
from worker.tasks import send_signal, create_table

load_dotenv()

API_KEY = os.getenv("API_KEY")
LOG_FILE = os.getenv("LOG_FILE", "log.txt")
PERCENT = float(os.getenv("PERCENT", 3))

INTERVAL_IN_MINUTE = 1
NUMBER_OF_COINS = 500
TIME_UPDATED_LIST_COINS = 60 * 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def init_redis(db):
    return redis.Redis(host="redis", port=6379, db=db, decode_responses=True)

r_coins = init_redis(0)
r_open = init_redis(1)
r_coins.flushdb()
r_open.flushdb()

COIN_CACHE = set()
CACHE_LOCK = asyncio.Lock()
history = []

async def get_list_coins():
    global COIN_CACHE
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
                headers={'X-CMC_PRO_API_KEY': API_KEY},
                params={"limit": NUMBER_OF_COINS}
            ) as response:
                response.raise_for_status()
                data = await response.json()
                async with CACHE_LOCK:
                    COIN_CACHE = {coin['symbol'] for coin in data.get('data', [])}
                    r_coins.sadd("coins", *COIN_CACHE)
                    r_coins.expire("coins", TIME_UPDATED_LIST_COINS)
        except Exception as e:
            logging.error(f"Ошибка получения списка монет: {e}")

def send_alert(message):
    if not ALERT_WEBHOOK:
        return
    try:
        requests.post(ALERT_WEBHOOK, json={"content": message})
    except Exception as e:
        logging.warning(f"Ошибка отправки webhook: {e}")

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

async def check_coin(coin):
    handler = TA_Handler(
        screener="crypto",
        exchange="BINANCE",
        symbol=f"{coin}USDT",
        interval=Interval.INTERVAL_1_MINUTE,
    )
    try:
        analysis = await asyncio.to_thread(handler.get_analysis)
        indicators = analysis.indicators
        open_price = float(indicators["open"])
        close_price = float(indicators["close"])
        
        pipe = r_open.pipeline()
        pipe.lpush(f"{coin}:history", open_price)
        pipe.ltrim(f"{coin}:history", 0, 9)
        await asyncio.to_thread(pipe.execute)
        
        open_stored = float(r_open.lindex(f"{coin}:history", 0) or open_price)
        change = (close_price - open_stored) / open_stored * 100

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

        return coin, change

    except Exception as e:
        logging.warning(f"Ошибка при анализе {coin}: {e}")
        return None

async def scanner_loop():
    minute = 0
    while True:
        start_time = time.time()
        minute += 1
        logging.info(f"Минута {minute}")
        
        if not COIN_CACHE:
            await get_list_coins()
        
        tasks = [check_coin(coin) for coin in COIN_CACHE]
        results = await asyncio.gather(*tasks)
        
        valid_results = [r for r in results if r is not None]
        if valid_results:
            history.extend(valid_results)
            plot_chart()
        
        elapsed = time.time() - start_time
        await asyncio.sleep(max(0, 60 - elapsed))

def update_coins_periodically():
    while True:
        time.sleep(TIME_UPDATED_LIST_COINS)
        asyncio.run(get_list_coins())

def run_scanner():
    asyncio.run(scanner_loop())

if __name__ == "__main__":
    create_table.delay()
    Thread(target=update_coins_periodically, daemon=True).start()
    run_scanner()
