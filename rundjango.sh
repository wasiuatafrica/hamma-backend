#!/bin/bash

#this scripts save from the stress of typing make migrations and migrate commands,
# To run this script, use ./rundjango.sh + name of commands (use all commands in the script)

# Ensure a command is provided as an argument
if [ -z "$1" ]; then
    echo "Usage: $0 <command>"
    exit 1
fi

# Run Django management command based on the provided argument
case "$1" in
    "makemigrations")
        python manage.py makemigrations
        ;;
    "migrate")
        python manage.py migrate
        ;;
    "test")
        python manage.py test
        ;;
    "runserver")
        python manage.py runserver
        ;;
    "all")
        # Run Django migrations
        python manage.py makemigrations
        python manage.py migrate

        # Run the development server
        python manage.py runserver
        ;;
    *)
        echo "Invalid command: $1"
        echo "Usage: $0 <makemigrations|migrate|runserver>"
        exit 1
        ;;
esac
