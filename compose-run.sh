#!/bin/bash

# Docker Compose wrapper for MC IP Scanner

case "$1" in
    "start")
        echo "🚀 Starting MC IP Scanner with Docker Compose..."
        docker-compose up -d
        echo "📋 Container started! Use './compose-run.sh logs' to view logs"
        echo "📋 Use './compose-run.sh stop' to stop the container"
        ;;
    "stop")
        echo "🛑 Stopping MC IP Scanner..."
        docker-compose down
        echo "✅ Container stopped"
        ;;
    "logs")
        echo "📋 Showing MC IP Scanner logs (Ctrl+C to exit)..."
        docker-compose logs -f mc-ip-scanner
        ;;
    "restart")
        echo "🔄 Restarting MC IP Scanner..."
        docker-compose restart
        echo "✅ Container restarted"
        ;;
    "status")
        echo "📋 Container status:"
        docker-compose ps
        ;;
    "build")
        echo "🔨 Building MC IP Scanner image..."
        docker-compose build
        echo "✅ Image built"
        ;;
    *)
        echo "MC IP Scanner Docker Compose Manager"
        echo ""
        echo "Usage: $0 {start|stop|logs|restart|status|build}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the scanner in background"
        echo "  stop    - Stop the scanner"
        echo "  logs    - Show real-time logs"
        echo "  restart - Restart the scanner"
        echo "  status  - Show container status"
        echo "  build   - Build the Docker image"
        echo ""
        echo "Examples:"
        echo "  $0 start    # Start scanner in background"
        echo "  $0 logs     # Watch logs in real-time"
        echo "  $0 stop     # Stop scanner gracefully"
        exit 1
        ;;
esac
