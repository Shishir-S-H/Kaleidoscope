#!/bin/bash

# DigitalOcean Deployment Script for Kaleidoscope AI
# Run this script on your DigitalOcean droplet

set -e

echo "🚀 Starting Kaleidoscope AI deployment on DigitalOcean..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (use sudo)"
    exit 1
fi

# Update system
print_status "Updating system packages..."
apt update && apt upgrade -y

# Install Docker
print_status "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    systemctl start docker
    systemctl enable docker
    print_status "Docker installed successfully"
else
    print_warning "Docker already installed"
fi

# Install Docker Compose
print_status "Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    print_status "Docker Compose installed successfully"
else
    print_warning "Docker Compose already installed"
fi

# Install Git
print_status "Installing Git..."
apt install git -y

# Clone repository
print_status "Cloning Kaleidoscope AI repository..."
if [ ! -d "Kaleidoscope" ]; then
    git clone https://github.com/Shishir-S-H/Kaleidoscope.git
    print_status "Repository cloned successfully"
else
    print_warning "Repository already exists, updating..."
    cd Kaleidoscope
    git pull
    cd ..
fi

# Navigate to project directory
cd Kaleidoscope/kaleidoscope-ai

# Create environment file
print_status "Setting up environment configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    print_warning "Please edit .env file with your actual values:"
    print_warning "nano .env"
    print_warning "Required: HF_API_TOKEN, REDIS_URL, ES_HOST"
    read -p "Press Enter after editing .env file..."
else
    print_warning ".env file already exists"
fi

# Configure firewall
print_status "Configuring firewall..."
ufw allow 22    # SSH
ufw allow 8001  # Content Moderation
ufw allow 8002  # Image Tagger
ufw allow 8003  # Scene Recognition
ufw allow 8004  # Image Captioning
ufw allow 8005  # Face Recognition
ufw allow 8006  # Post Aggregator
ufw allow 8007  # ES Sync
ufw allow 9200  # Elasticsearch
ufw --force enable

# Deploy services
print_status "Deploying Kaleidoscope AI services..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to start
print_status "Waiting for services to start..."
sleep 30

# Check service status
print_status "Checking service status..."
docker-compose -f docker-compose.prod.yml ps

# Test services
print_status "Testing services..."

# Test Redis
if docker exec kaleidoscope-ai-redis-1 redis-cli ping | grep -q "PONG"; then
    print_status "✅ Redis is running"
else
    print_error "❌ Redis is not responding"
fi

# Test Elasticsearch
if curl -s http://localhost:9200 | grep -q "elasticsearch"; then
    print_status "✅ Elasticsearch is running"
else
    print_error "❌ Elasticsearch is not responding"
fi

# Test AI Services
services=("8001:Content Moderation" "8002:Image Tagger" "8003:Scene Recognition" "8004:Image Captioning" "8005:Face Recognition" "8006:Post Aggregator" "8007:ES Sync")

for service in "${services[@]}"; do
    port=$(echo $service | cut -d: -f1)
    name=$(echo $service | cut -d: -f2)
    
    if curl -s http://localhost:$port/health | grep -q "healthy"; then
        print_status "✅ $name is running on port $port"
    else
        print_warning "⚠️  $name on port $port may not be ready yet"
    fi
done

print_status "🎉 Deployment completed!"
print_status "Your Kaleidoscope AI services are now running on DigitalOcean"
print_status "Check logs with: docker-compose -f docker-compose.prod.yml logs -f"
print_status "Monitor resources with: htop"

# Display connection information
echo ""
print_status "📋 Connection Information:"
echo "  - Content Moderation: http://$(curl -s ifconfig.me):8001"
echo "  - Image Tagger: http://$(curl -s ifconfig.me):8002"
echo "  - Scene Recognition: http://$(curl -s ifconfig.me):8003"
echo "  - Image Captioning: http://$(curl -s ifconfig.me):8004"
echo "  - Face Recognition: http://$(curl -s ifconfig.me):8005"
echo "  - Post Aggregator: http://$(curl -s ifconfig.me):8006"
echo "  - ES Sync: http://$(curl -s ifconfig.me):8007"
echo "  - Elasticsearch: http://$(curl -s ifconfig.me):9200"
