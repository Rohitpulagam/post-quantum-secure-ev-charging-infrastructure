# Multi-stage Dockerfile for ISO 15118 + PQC EV Charging System
# Stage 1: Build liboqs and oqs-provider
FROM ubuntu:22.04 AS builder

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    ninja-build \
    git \
    libssl-dev \
    python3-dev \
    python3-pip \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Build and install liboqs 0.15.0
WORKDIR /tmp
RUN git clone --depth 1 --branch 0.15.0 https://github.com/open-quantum-safe/liboqs.git && \
    cd liboqs && \
    mkdir build && cd build && \
    cmake -GNinja .. \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DBUILD_SHARED_LIBS=ON \
        -DOQS_BUILD_ONLY_LIB=ON && \
    ninja && \
    ninja install && \
    ldconfig

# Build and install OQS Provider for OpenSSL
RUN git clone --depth 1 https://github.com/open-quantum-safe/oqs-provider.git && \
    cd oqs-provider && \
    mkdir build && cd build && \
    cmake -GNinja .. \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DOPENSSL_ROOT_DIR=/usr && \
    ninja && \
    ninja install

# Stage 2: Runtime image
FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy liboqs and oqs-provider from builder
COPY --from=builder /usr/local/lib/liboqs.* /usr/local/lib/
COPY --from=builder /usr/local/lib/oqsprovider.* /usr/local/lib/
COPY --from=builder /usr/local/include/oqs /usr/local/include/oqs

# Update library cache
RUN ldconfig

# Set working directory
WORKDIR /app

# Create Python virtual environment
RUN python3 -m venv /app/venv

# Activate virtual environment for subsequent commands
ENV PATH="/app/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir liboqs-python==0.14.0

# Copy application code
COPY main.py .
COPY streamlit_app.py .
COPY run_streamlit.sh .
COPY cloud/ ./cloud/
COPY ev_station/ ./ev_station/
COPY ev_vehicle/ ./ev_vehicle/
COPY certs/ ./certs/
COPY scripts/ ./scripts/

# Make scripts executable
RUN chmod +x run_streamlit.sh scripts/*.sh

# Create directories for logs
RUN mkdir -p /app/logs

# Expose ports
# 8501: Streamlit web interface
# 9000: Cloud backend WebSocket
# 15118: Charging station (ISO 15118)
EXPOSE 8501 9000 15118

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# Default command: Run Streamlit interface
CMD ["streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
