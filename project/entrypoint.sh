#!/bin/sh

# Perform migrations
python manage.py makemigrations
python manage.py migrate

# Check if Stocks.object.all() returns an empty list
#if ! python -c "from portfolio.models import Stocks; exit(0) if Stocks.objects.all() else exit(1)"; then
    # If empty, create_stocks
 #   python manage.py create_stocks
#fi


# Execute the passed command
exec "$@"
