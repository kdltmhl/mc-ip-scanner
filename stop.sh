#!/bin/bash

# Stop script for MC IP Scanner Docker container

echo "🛑 Stopping MC IP Scanner..."

# Get container ID if running
CONTAINER_ID=$(docker ps -q -f name=mc-ip-scanner-run)

if [ -z "$CONTAINER_ID" ]; then
    echo "ℹ️  No running MC IP Scanner container found"

    # Check if there are any stopped containers with the same name
    STOPPED_CONTAINER=$(docker ps -a -q -f name=mc-ip-scanner-run)
    if [ -n "$STOPPED_CONTAINER" ]; then
        echo "🧹 Cleaning up stopped container..."
        docker rm "$STOPPED_CONTAINER"
        echo "✅ Cleaned up stopped container"
    fi

    exit 0
fi

echo "📋 Container ID: $CONTAINER_ID"

# Try graceful stop first (30 second timeout)
echo "🔄 Attempting graceful stop..."
if docker stop -t 30 mc-ip-scanner-run; then
    echo "✅ Container stopped gracefully"
else
    echo "⚠️  Graceful stop failed, force killing..."
    # Force kill if graceful stop fails
    docker kill mc-ip-scanner-run
    echo "🔥 Container force killed"
fi

# Clean up the container
docker rm mc-ip-scanner-run 2>/dev/null || true

echo "🎉 MC IP Scanner stopped and cleaned up"
