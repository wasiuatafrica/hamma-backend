release: python manage.py migrate
web: daphne backend.asgi:application --port $PORT --bind 0.0.0.0 -v2
worker: celery -A backend worker -l info --concurrency 2 
beat: celery -A backend beat
