# Docker Deployment Guide

## 🐋 Quick Start

### Build and Run (One Command)
```bash
./docker-run.sh
```

This will:
1. Build the Docker image (if not exists)
2. Start all services (Streamlit + Cloud + Station)
3. Display access URLs

Access the Streamlit interface at: **http://localhost:8501**

---

## 📦 Manual Build

### Build the Docker Image
```bash
./docker-build.sh
```

Or manually:
```bash
docker build -t pqc-iso15118:latest .
```

---

## 🚀 Running Services

### Option 1: Start All Services
```bash
docker-compose up -d
```

Services started:
- **Streamlit Interface** (Port 8501)
- **Cloud Backend** (Port 9000)
- **Charging Station** (Port 15118)

### Option 2: Start Specific Services
```bash
# Only Streamlit interface
docker-compose up -d streamlit

# Backend services (Cloud + Station)
docker-compose up -d cloud station

# Individual services
docker-compose up -d cloud
docker-compose up -d station
```

### Option 3: Run Vehicle Client (On-Demand)
```bash
docker-compose run --rm vehicle
```

This runs a single charging session and exits.

---

## 📊 Accessing Services

| Service | URL | Description |
|---------|-----|-------------|
| **Streamlit UI** | http://localhost:8501 | Web control panel |
| **Cloud Backend** | ws://localhost:9000 | WebSocket server |
| **Charging Station** | tls://localhost:15118 | TLS server (ISO 15118) |

---

## 📝 Viewing Logs

### Follow logs in real-time
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f streamlit
docker-compose logs -f cloud
docker-compose logs -f station
```

### View last N lines
```bash
docker-compose logs --tail=50 station
```

---

## 🛠️ Management Commands

### Stop Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

### Restart Specific Service
```bash
docker-compose restart station
```

### View Running Containers
```bash
docker-compose ps
```

### View Resource Usage
```bash
docker stats
```

### Remove Everything (including volumes)
```bash
docker-compose down -v
```

---

## 🔧 Docker Compose Configuration

### Services Defined

**streamlit** (Main control panel)
- Port: 8501
- Auto-restart: yes
- Health check: enabled

**cloud** (Certificate verification backend)
- Port: 9000
- Auto-restart: yes
- Health check: enabled

**station** (Charging station TLS server)
- Port: 15118
- Auto-restart: yes
- Depends on: cloud
- Health check: enabled

**vehicle** (Electric vehicle client)
- On-demand execution
- Depends on: station
- Auto-restart: no

### Network
- Network name: `pqc_network`
- Type: bridge
- Subnet: 172.28.0.0/16

---

## 🐛 Troubleshooting

### Check Container Status
```bash
docker-compose ps
```

### Check Health Status
```bash
docker inspect pqc_cloud --format='{{.State.Health.Status}}'
docker inspect pqc_station --format='{{.State.Health.Status}}'
```

### Enter Container Shell
```bash
docker exec -it pqc_streamlit bash
docker exec -it pqc_cloud bash
docker exec -it pqc_station bash
```

### Test Network Connectivity
```bash
# From station container, test cloud connection
docker exec pqc_station python3 -c "import socket; s = socket.socket(); s.connect(('cloud', 9000)); print('Connected!')"
```

### Rebuild Image (after code changes)
```bash
docker-compose build
docker-compose up -d
```

### Clean Build (no cache)
```bash
docker-compose build --no-cache
```

---

## 📁 Volume Mounts

Logs directory is mounted to host:
```
./logs:/app/logs
```

View logs on host:
```bash
ls -lh logs/
```

---

## 🔐 Security Notes

- Containers run with default user permissions
- Certificates are copied into the image (not mounted)
- Network is isolated (bridge network)
- For production: Consider using secrets management
- For production: Run containers as non-root user

---

## 🌐 Network Deployment

### Expose to Network
Edit `docker-compose.yml` and change ports:

```yaml
ports:
  - "0.0.0.0:8501:8501"  # Accessible from network
```

### Access from Other Machines
```
http://YOUR_SERVER_IP:8501
```

---

## ⚡ Performance

### Image Size
Approximately 800-900 MB (includes liboqs, Python, dependencies)

### Memory Usage
- Streamlit: ~200-300 MB
- Cloud: ~50-100 MB
- Station: ~100-150 MB

### Startup Time
- Image build: 5-10 minutes (first time)
- Container start: 2-5 seconds

---

## 🧪 Testing

### Run Complete Test
```bash
# Start backend
docker-compose up -d cloud station

# Run vehicle test
docker-compose run --rm vehicle

# Check logs
docker-compose logs station
```

### Multiple Vehicle Sessions
```bash
# Run 3 charging sessions
for i in {1..3}; do
  echo "Session $i"
  docker-compose run --rm vehicle
  sleep 2
done
```

---

## 🔄 CI/CD Integration

### Build in CI/CD Pipeline
```bash
docker build -t pqc-iso15118:${VERSION} .
docker tag pqc-iso15118:${VERSION} registry.example.com/pqc-iso15118:${VERSION}
docker push registry.example.com/pqc-iso15118:${VERSION}
```

### Run Tests in CI
```bash
docker-compose up -d cloud station
sleep 5
docker-compose run --rm vehicle
TEST_RESULT=$?
docker-compose down
exit $TEST_RESULT
```

---

## 📋 Requirements

- **Docker**: 20.10+
- **Docker Compose**: 1.29+ or Docker Compose V2
- **Disk Space**: ~1.5 GB (image + containers)
- **RAM**: 1 GB minimum, 2 GB recommended

---

## 🎯 Use Cases

### 1. Development
```bash
# Start services
docker-compose up -d

# Make code changes on host
# (mount volumes for live reload if needed)

# Rebuild and restart
docker-compose build
docker-compose up -d
```

### 2. Testing
```bash
# Run automated tests
docker-compose run --rm vehicle
```

### 3. Demo/Presentation
```bash
# One command to start everything
./docker-run.sh

# Show in browser
open http://localhost:8501
```

### 4. Production
```bash
# Use production compose file
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📚 Additional Commands

### Export Image
```bash
docker save pqc-iso15118:latest | gzip > pqc-iso15118.tar.gz
```

### Import Image
```bash
docker load < pqc-iso15118.tar.gz
```

### Prune Unused Resources
```bash
docker system prune -a
```

---

## ✅ Verification Checklist

After starting services, verify:

- [ ] `docker-compose ps` shows all containers running
- [ ] `curl http://localhost:8501` returns content
- [ ] `docker-compose logs cloud` shows "listening on 0.0.0.0:9000"
- [ ] `docker-compose logs station` shows "Connected to cloud"
- [ ] Streamlit interface accessible in browser
- [ ] Can run vehicle test: `docker-compose run --rm vehicle`

---

**Happy Dockerizing! 🐋⚡🔐**
