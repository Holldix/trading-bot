# TradingViewBot

Этот бот предназначен для отслеживания пампов или дампов (резкий взлёт или падение цены) в нескольких десятках криптовалютах сразу с последующим принятием решения для отторговки резкого движения цены. Вы можете настроить бота под себя. Например, можно изменить интервал движения цены, а также процент, на сколько изменится цена за этот интервал.

Точность движения цены - 1 минута.

## Как запустить бота

Чтобы запустить бота на своём компьютере, вам необходимо сделать следующее:

1. Зарегистрировать бота в телеграмм и получить API ключ
2. Зарегистрироваться на CoinMarketCap и получить API ключ
3. Установить DockerHub
4. Скачать и распаковать репозиторий
5. Добавить файл .env в корень папки, и написать в него следующее:

~~~env
TOKEN_BOT = "<API от телеграм бота>"
API_KEY = "<API от CoinMarketCap>"
~~~

6. Открываем командную строку и прописываем следующие команды:

~~~cmd
cd <путь папки, где лежит репозиторий>
docker compose up
~~~

Готово, бот запущен! Теперь остаётся открыть бота в телеграме и прописать команду */start* Теперь уведомления о пампах и дампах будет приходить к вам в телеграм

## Как работает бот

1. Получает список топ криптовалют (далее монеты) по капитализации с сайта *CoinMarketCap* и сохранет его в *Redis* на 1 час, затем идёт обновление списка.
2. Высчитывает движение цены монеты в верх и вниз.
    1. Если изменение цены больше триггера, то назначается задача в *Celery* на отправку сообщения всем зарегистрировавшемся в телеграм боте.
    2. После, значение текущей цены сохраняется в *Redis*, а значение последней цены удаляется. В данном случае *Redis* работает по принципу очереди.
3. Далее пункт 2 повторяется до бесконечности.

## Какие гиперпараметры можно изменять

**INTERVAL_IN_MINUTE** - период времени в минутах, за который высчитывается изменение цены

**PERCENT** - процент (триггер)

**NUMBER_OF_COINS** - количество монет, которые бот получает из *CoinMarketCap*

**TIME_UPDATED_LIST_COINS** - время в минутах, на которое сохраняется список топ криптовалют
