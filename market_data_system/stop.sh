#!/bin/bash

# Send shutdown notification
echo "Sending shutdown notification..."
cd /path/to/market_data_system
python -c "from tasks.scheduled_tasks import send_shutdown_notification; send_shutdown_notification.delay()"

# Wait for notification to be sent
sleep 5

# Stop FastAPI server
echo "Stopping FastAPI server..."
pkill -f "uvicorn app.main:app"

# Stop Celery worker and beat
echo "Stopping Celery processes..."
pkill -f "celery -A tasks.celery_app"

# Stop Redis server
echo "Stopping Redis server..."
redis-cli shutdown

echo "Market data system stopped successfully!"