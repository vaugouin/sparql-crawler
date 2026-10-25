#!/bin/bash

# Switched off by off.sh, back on with on.sh: the flag file CRON_OFF next to this script makes
# every cron tick exit here. The script keeps its name, so the git clone stays clean.
if [ -f "$(dirname "$(readlink -f "$0")")/CRON_OFF" ]; then
    echo "CRON_OFF present: sparql-crawler switched off (bash on.sh to switch it back on)."
    exit 0
fi

# Check if the sparql-crawler Docker container is running
if [ $(docker ps -q -f name=sparql-crawler) ]; then
    echo "sparql-crawler Docker container is already running."
else
    # Start the sparql-crawler container if it is not running
    cd /home/debian/docker/sparql-crawler
    docker build -t sparql-crawler-python-app .
    # Secrets are injected at runtime via --env-file; the .env file is NOT baked into the image (see .dockerignore).
    # docker run -it --rm --network="host" --env-file /home/debian/docker/sparql-crawler/.env --name sparql-crawler sparql-crawler-python-app
    docker run -d --rm --network="host" --env-file /home/debian/docker/sparql-crawler/.env --name sparql-crawler sparql-crawler-python-app
    echo "sparql-crawler Docker container started."
fi
