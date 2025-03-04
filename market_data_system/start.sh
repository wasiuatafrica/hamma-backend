#!/bin/bash

# Start Redis Server
echo "Starting Redis server..."
redis-server --daemonize yes

# Wait for Redis to start
sleep 2

# Start Celery worker
echo "Starting Celery worker..."
#cd market_data_system
celery -A tasks.celery_app worker --loglevel=info --detach

# Start Celery beat
echo "Starting Celery beat..."
#cd market_data_system
celery -A tasks.celery_app beat --loglevel=info --detach

# Start FastAPI server
echo "Starting FastAPI server..."
#cd market_data_system
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 &

# Send startup notification
echo "Sending startup notification..."
#cd market_data_system
python -c "from tasks.scheduled_tasks import send_startup_notification; send_startup_notification.delay()"

echo "Market data system started successfully!"