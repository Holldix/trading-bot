from celery import Celery


app = Celery("work",
             broker="redis://redis:6379/10",
             include=["worker.tasks"])

if __name__ == "__main__":
    app.start()
