#!/bin/bash

echo "Starting Gene Editing Ethics Symposium Minutes System..."

if [ ! -f .env ]; then
    echo "Warning: .env file not found. Copying from .env.example..."
    cp .env.example .env
fi

mkdir -p uploads output archive logs

echo "Starting services with Docker Compose..."
docker-compose up -d

echo "Services started!"
echo "Frontend: http://localhost"
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Luigi Scheduler: http://localhost:8082"
