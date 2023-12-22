release: python manage.py migrate
web: daphne backend.asgi:application --port $PORT --bind 0.0.0.0 -v2
worker: celery -A backend worker  -loglevel info 
beat: celery -A backend beat