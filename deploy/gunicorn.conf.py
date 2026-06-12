import multiprocessing
import os


bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")
worker_class = "sync"
workers = int(os.getenv("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count() // 2)))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Send logs to stdout/stderr so systemd/journald captures them.
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Prevent runaway temp file growth on small pilot instances.
worker_tmp_dir = "/dev/shm"
