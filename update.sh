#!/bin/bash

git pull origin main

docker compose -f prod.yml up -d --build

docker rmi $(docker images -f "dangling=true" -q)
