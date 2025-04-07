from celery import Celery

app = Celery(
    "worker",
    broker="redis://redis:6379/10",
    backend=None,
    task_ignore_result=True,
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True
    },
    task_routes={
        'worker.tasks.send_signal': {'queue': 'high_priority'},
        'worker.tasks.*': {'queue': 'default'}
    }
)

if __name__ == "__main__":
    app.start()
