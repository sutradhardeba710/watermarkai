#!/bin/bash
set -e

echo "Starting Video Watermark AI Production Deployment..."

# Change to the project root directory
cd "$(dirname "$0")/.."

# Ensure log directory exists
mkdir -p .run-logs

# Check arguments
if [[ "$1" != "worker" && "$1" != "api" ]]; then
    echo "Usage: $0 [api|worker]"
    echo "Please specify whether this instance should run the API or Worker."
    exit 1
fi

echo "Building Docker images..."
docker compose -f docker-compose.prod.yml --profile $1 build

if [[ "$1" == "api" ]]; then
    echo "Running database migrations..."
    docker compose -f docker-compose.prod.yml --profile api run --rm backend python -m alembic upgrade head

    echo "Starting FastAPI Backend..."
    docker compose -f docker-compose.prod.yml --profile api up -d
elif [[ "$1" == "worker" ]]; then
    echo "Starting Celery Worker and Beat..."
    docker compose -f docker-compose.prod.yml --profile worker up -d
fi

echo "Services started successfully."
