#!/bin/bash

docker compose -f local.yml up -d --build

docker rmi $(docker images -f "dangling=true" -q)
