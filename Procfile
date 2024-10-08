release: python manage.py migrate
web: bin/start-pgbouncer-stunnel daphne backend.asgi:application --port $PORT --bind 0.0.0.0 -v1
worker: celery -A backend worker -B -l warning --concurrency 2
