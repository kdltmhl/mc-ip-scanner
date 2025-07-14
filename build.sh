#!/bin/bash

# Build script for MC IP Scanner Docker container

echo "Building MC IP Scanner Docker container..."

# Build the Docker image
docker build -t mc-ip-scanner:latest .

if [ $? -eq 0 ]; then
    echo "✅ Docker image built successfully!"
    echo "🐳 Image: mc-ip-scanner:latest"
    echo ""
    echo "Next steps:"
    echo "1. Copy .env.docker to .env and fill in your Discord credentials"
    echo "2. Run: docker-compose up -d"
    echo "   OR"
    echo "3. Run: ./run.sh [your-arguments]"
else
    echo "❌ Docker build failed!"
    exit 1
fi
