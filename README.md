# Anyon Backend

clone this repository

change directory to the cloned repository

run docker compose -f local.yml up -d --build

if running first time:

    run docker ps to get the container id of the web 

    run docker exec -it <container-id> python manage.py create_stocks
