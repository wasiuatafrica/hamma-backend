#!/bin/bash

cd Anyon-Admin

git pull origin main

docker-compose -f prod.yml up -d --build

docker rmi $(docker images -f "dangling=true" -q)
