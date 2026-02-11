#!/bin/bash
# Docker build and deployment script for ISO 15118 + PQC

set -e

echo "=========================================="
echo "ISO 15118 + PQC Docker Build Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

print_info "Docker is installed"

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

print_info "Docker Compose is installed"

# Check if certificates exist
if [ ! -d "certs" ] || [ ! -f "certs/ca.pem" ]; then
    print_warning "Certificates not found. Generating certificates..."
    cd scripts
    ./gen_certs.sh
    cd ..
    print_info "Certificates generated"
else
    print_info "Certificates found"
fi

# Build Docker image
echo ""
print_info "Building Docker image..."
docker build -t pqc-iso15118:latest .

if [ $? -eq 0 ]; then
    print_info "Docker image built successfully"
else
    print_error "Docker image build failed"
    exit 1
fi

# Show image size
echo ""
IMAGE_SIZE=$(docker images pqc-iso15118:latest --format "{{.Size}}")
print_info "Image size: $IMAGE_SIZE"

echo ""
echo "=========================================="
echo "Build Complete!"
echo "=========================================="
echo ""
echo "Available commands:"
echo ""
echo "1. Start all services:"
echo "   docker-compose up -d"
echo ""
echo "2. Start only Streamlit interface:"
echo "   docker-compose up -d streamlit"
echo ""
echo "3. Start Cloud + Station (backend):"
echo "   docker-compose up -d cloud station"
echo ""
echo "4. Run a vehicle charging session:"
echo "   docker-compose run --rm vehicle"
echo ""
echo "5. View logs:"
echo "   docker-compose logs -f [service_name]"
echo ""
echo "6. Stop all services:"
echo "   docker-compose down"
echo ""
echo "7. Access Streamlit interface:"
echo "   http://localhost:8501"
echo ""
echo "=========================================="
