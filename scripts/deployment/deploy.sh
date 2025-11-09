#!/bin/bash

echo "================================================"
echo "   Kaleidoscope AI - Production Deployment"
echo "================================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    echo ""
    echo "Quick setup:"
    echo "  cp .env.example .env"
    echo "  nano .env  # Add your tokens"
    exit 1
fi

# Load environment
set -a
source .env
set +a

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running!"
    exit 1
fi

# Pull latest images
echo "📥 Pulling latest Docker images..."
docker-compose -f docker-compose.prod.yml pull

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down

# Start services
echo "🚀 Starting services..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services
echo "⏳ Waiting for services to initialize..."
sleep 15

# Check status
echo ""
echo "📊 Service Status:"
docker-compose -f docker-compose.prod.yml ps

echo ""
echo "================================================"
echo "   ✅ Deployment Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "  • Check logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "  • Run tests: python3 tests/test_end_to_end.py"
echo "  • Monitor: docker stats"
echo ""
