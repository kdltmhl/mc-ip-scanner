#!/bin/bash

# Run script for MC IP Scanner Docker container

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please copy .env.docker to .env and fill in your Discord credentials"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo "🛑 Stopping MC IP Scanner..."
    docker stop mc-ip-scanner-run 2>/dev/null || true
    docker rm mc-ip-scanner-run 2>/dev/null || true
    exit 0
}

# Trap signals to ensure cleanup
trap cleanup SIGINT SIGTERM EXIT

echo "🔧 Setting up permissions..."
mkdir -p checkpoints logs
chmod 755 checkpoints logs
chmod 666 checkpoints/* 2>/dev/null || true  # Ignore errors if no files exist

# Check if Docker image exists
if ! docker image inspect mc-ip-scanner:latest > /dev/null 2>&1; then
    echo "🔨 Docker image not found. Building..."
    ./build.sh
fi

# Check if container is already running
if docker ps -q -f name=mc-ip-scanner-run | grep -q .; then
    echo "❌ Container 'mc-ip-scanner-run' is already running!"
    echo "💡 Use './stop.sh' to stop it first, or 'docker ps' to see running containers"
    exit 1
fi

echo "🚀 Starting MC IP Scanner..."
echo "💡 Press Ctrl+C to stop gracefully"

# Run the container with passed arguments
# --init ensures proper signal handling
# --sig-proxy=true forwards signals to the container
docker run --rm -it \
    --init \
    --sig-proxy=true \
    --name mc-ip-scanner-run \
    --env-file .env \
    -v $(pwd)/checkpoints:/app/checkpoints \
    -v $(pwd)/logs:/app/logs \
    mc-ip-scanner:latest "$@"
