#!/bin/bash
# Quick start script for Docker deployment

set -e

echo "=========================================="
echo "ISO 15118 + PQC - Docker Quick Start"
echo "=========================================="
echo ""

# Check if image exists
if ! docker images | grep -q "pqc-iso15118"; then
    echo "Docker image not found. Building..."
    ./docker-build.sh
fi

echo "Starting services..."
echo ""

# Start services
docker-compose up -d

echo ""
echo "=========================================="
echo "Services Started!"
echo "=========================================="
echo ""
echo "📊 Streamlit Interface: http://localhost:8501"
echo "☁️  Cloud Backend:      ws://localhost:9000"
echo "🔌 Charging Station:    tls://localhost:15118"
echo ""
echo "View logs:"
echo "  docker-compose logs -f streamlit"
echo "  docker-compose logs -f cloud"
echo "  docker-compose logs -f station"
echo ""
echo "Run a vehicle charging session:"
echo "  docker-compose run --rm vehicle"
echo ""
echo "Stop services:"
echo "  docker-compose down"
echo ""
echo "=========================================="
