#!/bin/sh

# Perform migrations
python manage.py makemigrations
python manage.py migrate


# Execute the passed command
exec "$@"
