#!/bin/bash

# Check if the sparql-crawler Docker container is running
if [ $(docker ps -q -f name=sparql-crawler) ]; then
    echo "sparql-crawler Docker container is already running."
else
    # Start the sparql-crawler container if it is not running
    cd /home/debian/docker/sparql-crawler
    docker build -t sparql-crawler-python-app .
    # docker run -it --rm --network="host" --name sparql-crawler sparql-crawler-python-app
    docker run -d --rm --network="host" --name sparql-crawler sparql-crawler-python-app
    echo "sparql-crawler Docker container started."
fi
