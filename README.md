# ISO 15118 + Post-Quantum Cryptography (PQC) - EV Charging System

A complete Python implementation of the ISO 15118 electric vehicle charging communication protocol with Post-Quantum Cryptography integration using Falcon-512 signatures.

**🔐 Security:** Hybrid quantum-safe architecture with classical TLS 1.3 transport + Falcon-512 PQC signatures  
**📡 Protocol:** ISO 15118-2:2014 compliant 5-phase charging protocol  
**🚀 Performance:** Complete charging session in ~570ms with cloud-based certificate verification  
**☁️ Architecture:** Simplified cloud backend for certificate verification and logging only

---

## 🎯 Project Overview

This system demonstrates quantum-safe EV charging communication with three components:

1. **Cloud Backend** - WebSocket server for certificate verification & logging (Port 9000)
2. **Charging Station (SECC)** - TLS server with PQC signatures (Port 15118)
3. **Electric Vehicle (EVCC)** - TLS client with PQC signatures (Client)

### Simplified Architecture (2026)

```
┌──────────────────────┐
│   Cloud Backend      │ 
│   Port 9000          │
│   • Certificate      │
│     verification     │
│   • Logging only     │
└──────┬───────────────┘
       │
       │ Simple WebSocket
       │ (JSON messages, no PQC/ISO15118)
       │
┌──────▼───────────────────────┐
│  Charging Station (SECC)     │
│  Port 15118                  │
│  • Generates OWN PQC keys    │ ◄─── TLS 1.3 + ISO 15118
│  • Falcon-512 signatures     │      PQC Signatures (Falcon-512)
│  • Forwards cert to cloud    │
└──────┬───────────────────────┘
       │
       │ TLS 1.3 Connection
       │ ISO 15118 Protocol
       │
┌──────▼───────────────────────┐
│  Electric Vehicle (EVCC)     │
│  Client                      │
│  • Falcon-512 verify         │
│  • PQC certificate signing   │
└──────────────────────────────┘
```

**Key Design Decisions:**
- ✅ Station generates its own PQC keys (no key distribution needed)
- ✅ Cloud-Station: Simple WebSocket (JSON-RPC style, local network only)
- ✅ Station-Vehicle: Full ISO 15118 + PQC (Falcon-512 signatures)
- ✅ Cloud verifies vehicle certificates on-demand
- ✅ System works with or without cloud (graceful degradation)

---

## 🔐 Security Implementation

### Current Architecture (Hybrid Quantum-Safe)

| Layer | Technology | Quantum-Safe? | Notes |
|-------|------------|---------------|-------|
| **Transport** | TLS 1.3 (ECDHE-P256, ECDSA) | ❌ Classical | Proven, compatible |
| **Cipher** | TLS_AES_256_GCM_SHA384 | ✅ Quantum-resistant | 256-bit security |
| **Application Signatures** | Falcon-512 (NIST PQC) | ✅ Quantum-safe | All messages signed |
| **Message Authentication** | Falcon-512 | ✅ Quantum-safe | Cannot be forged |
| **Certificate Verification** | Cloud-based Falcon-512 | ✅ Quantum-safe | Centralized security |

**Result:** Application-layer messages are quantum-safe. Transport layer uses proven classical TLS.

### Why This Approach?

Pure PQC TLS certificates (ML-DSA) cannot be used because:
- Python's `ssl` module doesn't support PQC key formats
- OpenSSL with OQS provider has certificate encoding issues
- Version mismatch: liboqs 0.15.0 vs liboqs-python 0.14.0

**Solution:** Use classical TLS for transport + PQC signatures for application-layer security. This provides quantum-safe authentication while maintaining compatibility.

### Performance Metrics

- **Full Session Time:** ~570ms (all 5 ISO 15118 phases)
- **TLS Handshake:** ~12ms
- **PQC Signature Generation:** ~8ms (Falcon-512)
- **PQC Signature Verification:** ~3ms (Falcon-512)
- **Cloud Verification:** ~6ms (over WebSocket)
- **Signature Size:** ~666 bytes (Falcon-512)

---

## 🛠️ Installation & Setup

### System Requirements
- **OS:** Linux (Ubuntu 20.04+/Debian 11+)
- **Python:** 3.10+ (tested with 3.12.3)
- **OpenSSL:** 3.0+
- **CMake:** 3.12+
- **GCC/Clang:** C/C++ compiler

### Step 1: Install liboqs (Open Quantum Safe Library)

liboqs provides the core PQC algorithms (Falcon, Dilithium, Kyber).

```bash
# Install dependencies
sudo apt update
sudo apt install -y cmake gcc g++ libssl-dev ninja-build

# Clone liboqs
cd /tmp
git clone --depth 1 --branch 0.15.0 https://github.com/open-quantum-safe/liboqs.git
cd liboqs

# Build and install
mkdir build && cd build
cmake -GNinja .. \
  -DCMAKE_INSTALL_PREFIX=/usr/local \
  -DBUILD_SHARED_LIBS=ON \
  -DOQS_BUILD_ONLY_LIB=ON
ninja
sudo ninja install
sudo ldconfig

# Verify installation
ls -lh /usr/local/lib/liboqs.*
```

**Version Installed:** liboqs 0.15.0

### Step 2: Install OQS Provider for OpenSSL

The OQS Provider enables OpenSSL to use PQC algorithms.

```bash
# Clone OQS Provider
cd /tmp
git clone --depth 1 https://github.com/open-quantum-safe/oqs-provider.git
cd oqs-provider

# Build and install
mkdir build && cd build
cmake -GNinja .. \
  -DCMAKE_INSTALL_PREFIX=/usr/local \
  -DOPENSSL_ROOT_DIR=/usr
ninja
sudo ninja install

# Configure OpenSSL to load OQS provider
sudo mkdir -p /usr/lib/ssl
sudo tee /usr/lib/ssl/openssl.cnf > /dev/null << 'EOF'
openssl_conf = openssl_init

[openssl_init]
providers = provider_sect

[provider_sect]
default = default_sect
oqsprovider = oqsprovider_sect

[default_sect]
activate = 1

[oqsprovider_sect]
activate = 1
EOF

# Set environment variable (add to ~/.bashrc for persistence)
export OPENSSL_CONF=/usr/lib/ssl/openssl.cnf

# Verify OQS provider is loaded
openssl list -providers

# Expected output:
# Providers:
#   default
#     name: OpenSSL Default Provider
#     ...
#   oqsprovider
#     name: OpenSSL OQS Provider
#     ...
```

**OQS Provider Status:** Installed and loaded by OpenSSL

### Step 3: Setup Python Environment

```bash
# Navigate to project directory
cd /home/rohit-pulagam/Downloads/pqc_iso15118

# Create Python virtual environment
python3 -m venv niso

# Activate environment
source niso/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
pip install cryptography==46.0.5
pip install websockets==16.0
pip install cffi pycparser

# Install liboqs-python
pip install liboqs-python==0.14.0

# Verify installation
python -c "import oqs; print(f'liboqs-python: {oqs.__version__}')"
python -c "import oqs; print('Available signatures:', oqs.get_enabled_sig_mechanisms())"
```

**Python Environment:** niso (venv)  
**liboqs-python Version:** 0.14.0  
**Note:** Version mismatch with liboqs 0.15.0 causes certificate encoding issues but doesn't affect signature operations.

### Step 4: Generate Certificates

```bash
# Generate classical ECDSA certificates (WORKING)
cd scripts
./gen_certs.sh

# This creates certificates in certs/ directory:
# - ca.pem (Certificate Authority)
# - secc_cert.pem, secc_key.pem (Charging Station)
# - evcc_cert.pem, evcc_key.pem (Electric Vehicle)

# Optional: Generate PQC certificates (for testing only, not usable)
cd ..
./generate_pqc_certs.sh mldsa44 false

# This creates certificates in certs_pqc/ directory
# Note: These have encoding errors and cannot be used with OpenSSL
```

---

## 🚀 Running the System

### Quick Start (3 Terminals)

**Terminal 1 - Cloud Backend (Optional):**
```bash
cd /home/rohit-pulagam/Downloads/pqc_iso15118
source niso/bin/activate
python main.py --mode cloud --host 0.0.0.0 --port 9000
```
*Cloud runs on port 9000 and handles certificate verification via WebSocket*

**Terminal 2 - Charging Station (SECC):**
```bash
cd /home/rohit-pulagam/Downloads/pqc_iso15118
source niso/bin/activate
python main.py --mode station --host 0.0.0.0 --port 15118 \
  --cloud-host localhost --cloud-port 9000 --pqc
```
*Station runs on port 15118, connects to cloud at 9000, generates own PQC keys*

**Terminal 3 - Electric Vehicle (EVCC):**
```bash
cd /home/rohit-pulagam/Downloads/pqc_iso15118
source niso/bin/activate
python main.py --mode vehicle --host localhost --port 15118 --pqc
```
*Vehicle connects to station at port 15118 with PQC enabled*

### Running Without Cloud (Local Mode)

The system works perfectly without the cloud backend:

```bash
# Terminal 1 - Station (no cloud connection)
python main.py --mode station --host 0.0.0.0 --port 15118 --pqc

# Terminal 2 - Vehicle
python main.py --mode vehicle --host localhost --port 15118 --pqc
```
*Station will log that cloud is unavailable but continues operation normally*

### Expected Output from Vehicle

```
2026-02-12 03:42:15,123 [INFO] crypto: Using PQC signature algorithm: Falcon-512
2026-02-12 03:42:15,135 [INFO] vehicle: PHASE 1 (Protocol Negotiation) took 1.52 ms
2026-02-12 03:42:15,136 [INFO] vehicle: Negotiated algorithms: SIGN=Falcon-512 KEM=Kyber512 MODE=PQC_ONLY
2026-02-12 03:42:15,136 [INFO] crypto: Using PQC signature algorithm: Falcon-512
2026-02-12 03:42:15,144 [INFO] vehicle: PHASE 2 (Algorithm Negotiation) took 8.43 ms
2026-02-12 03:42:15,145 [INFO] vehicle: PHASE 3 (Certificate Exchange) took 0.62 ms
2026-02-12 03:42:15,146 [INFO] vehicle: PHASE 4 (Authorization) took 1.15 ms
2026-02-12 03:42:15,718 [INFO] vehicle: PHASE 5 (Charging + Stop) took 572.08 ms
2026-02-12 03:42:15,718 [INFO] vehicle: TOTAL SESSION TIME: 575.21 ms
```

### Success Indicators ✅

- **TLS Version:** TLSv1.3
- **Cipher Suite:** TLS_AES_256_GCM_SHA384
- **PQC Algorithm:** Falcon-512 (appears twice during crypto initialization)
- **Negotiated Mode:** PQC_ONLY
- **All 5 Phases Complete**
- **Session Time:** ~570-580ms
- **Cloud Verification:** "VERIFIED" in station logs (if cloud connected)

---

## 📋 ISO 15118 Protocol Flow

### 5-Phase Charging Protocol

**Phase 1: Protocol Negotiation (1-2 ms)**
- Vehicle sends `SupportedAppProtocolReq` with ISO 15118-2
- Station responds with `SupportedAppProtocolRes` (ACCEPTED)

**Phase 2: Algorithm Negotiation (4-9 ms)**
- Vehicle proposes PQC algorithms: Falcon-512, Kyber512
- Station selects algorithms and mode (PQC_ONLY/HYBRID/CLASSICAL)
- Both sides generate Falcon-512 keypairs

**Phase 3: Certificate Exchange (~1 ms)**
- Vehicle sends certificate with PQC public key
- Station verifies and responds with verification result

**Phase 4: Authorization (~1 ms)**
- Vehicle sends authorization request (simulated payment)
- Station authorizes and responds with result

**Phase 5: Charging + Session Stop (~503 ms)**
- Vehicle sends `ChargingReq` (simulates 500ms charging)
- Station responds with `ChargingRes`
- Vehicle sends `SessionStopReq`
- Station responds with `SessionStopRes`

### V2GTP Message Framing

All ISO 15118 messages use V2GTP (Vehicle-to-Grid Transfer Protocol) framing:

```
┌────────┬────────┬─────────────┬────────────┬──────────┐
│ 0x01   │ 0xFE   │ 0x80 0x01   │ Length(4B) │ Payload  │
├────────┼────────┼─────────────┼────────────┼──────────┤
│Version │Inverse │Payload Type │Big-Endian  │XML Data  │
└────────┴────────┴─────────────┴────────────┴──────────┘
```

- **Header Size:** 8 bytes
- **Payload Type:** 0x8001 (XML/EXI)
- **Max Payload:** 10 MB
- **Timeout:** 30 seconds per operation

---

## 🔬 OQS + TLS Integration Details

### How OQS Provider Works with OpenSSL

The OQS Provider extends OpenSSL's cryptographic capabilities:

```
┌─────────────────────────────────────────────┐
│           OpenSSL 3.x Core                  │
│  (TLS Protocol, X.509, Certificate Mgmt)    │
└────────────────┬────────────────────────────┘
                 │
                 ↓ Provider API
    ┌────────────────────────────────┐
    │     OQS Provider               │
    │  - ML-DSA (Dilithium)          │
    │  - Falcon                      │
    │  - ML-KEM (Kyber)              │
    │  - SPHINCS+                    │
    └────────────────┬───────────────┘
                     │
                     ↓ liboqs API
          ┌──────────────────────┐
          │      liboqs          │
          │  (C Implementation)  │
          └──────────────────────┘
```

### Current Integration Status

**✅ Working:**
- OQS provider loaded by OpenSSL
- liboqs algorithms available via Python (liboqs-python)
- Falcon-512 signatures used in application layer
- Sign/verify operations working perfectly

**❌ Not Working:**
- PQC certificates in TLS handshake
- OpenSSL loading ML-DSA private keys
- Python ssl module with PQC key formats

**Why PQC TLS Certificates Fail:**

1. **Certificate Generation:**
   ```bash
   openssl genpkey -algorithm mldsa44 -out key.pem -provider oqsprovider
   # Creates key but with encoding issues
   ```

2. **OpenSSL Server Attempt:**
   ```bash
   openssl s_server -cert cert.pem -key key.pem -provider oqsprovider
   # Error: unknown certificate type (0A0000F7)
   ```

3. **Root Causes:**
   - liboqs 0.15.0 and liboqs-python 0.14.0 version mismatch
   - ML-DSA OIDs not recognized by OpenSSL X.509 parser
   - ASN.1 encoding incompatibility in certificate structure

### Application-Layer PQC Implementation

Since TLS layer cannot use PQC certificates, we implement PQC at the application layer:

```python
# File: ev_station/crypto.py

class CryptoSuite:
    def generate(self):
        """Generate Falcon-512 keypair using liboqs"""
        if 'PQC' in self.cfg.mode.upper():
            self._oqs_sign = oqs.Signature('Falcon-512')
            pk = self._oqs_sign.generate_keypair()
            # Private key stays in oqs.Signature object
            self._pub = pk
    
    def sign(self, data: bytes) -> bytes:
        """Sign data with Falcon-512"""
        return self._oqs_sign.sign(data)
    
    def verify(self, data: bytes, sig: bytes, pubkey: bytes) -> bool:
        """Verify Falcon-512 signature"""
        return self._oqs_sign.verify(data, sig, pubkey)
```

**Message Flow with PQC Signatures:**

```
EVCC                                    SECC
 │                                       │
 ├─── TLS 1.3 Handshake (Classical) ───→│
 │←── TLS Established ───────────────────┤
 │                                       │
 ├─── ISO15118: AlgorithmNegReq ───────→│
 │     (Propose: Falcon-512)             │
 │←── AlgorithmNegRes ───────────────────┤
 │     (Selected: Falcon-512, PQC_ONLY)  │
 │                                       │
 │    [Both generate Falcon-512 keys]    │
 │                                       │
 ├─── CertExchangeReq ─────────────────→│
 │     + Public Key (Falcon-512)         │
 │     + Signature (Falcon-512)          │
 │                                       │
 │                      [Verify Signature]│
 │←── CertExchangeRes ────────────────────┤
 │     (Verification: SUCCESS)           │
 │                                       │
 ├─── AuthorizationReq ─────────────────→│
 │     + Signature (Falcon-512)          │
 │                                       │
 │                      [Verify Signature]│
 │←── AuthorizationRes ───────────────────┤
```

**Every ISO 15118 message is signed with Falcon-512, providing quantum-safe authentication.**

---

## 🔧 Technical Details

### Falcon-512 Characteristics

| Property | Value |
|----------|-------|
| **Type** | Digital Signature (lattice-based) |
| **Security Level** | NIST Level 1 (~128-bit) |
| **Public Key Size** | 897 bytes |
| **Signature Size** | ~666 bytes |
| **Sign Time** | ~1-2 ms |
| **Verify Time** | ~0.1-0.2 ms |
| **Standardization** | NIST PQC Competition Finalist |

### TLS Configuration

**Server (Charging Station):**
```python
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.verify_mode = ssl.CERT_REQUIRED  # Mutual authentication
ctx.minimum_version = ssl.TLSVersion.TLSv1_2
ctx.maximum_version = ssl.TLSVersion.TLSv1_3
ctx.load_cert_chain("certs/secc_cert.pem", "certs/secc_key.pem")
ctx.load_verify_locations("certs/ca.pem")
```

**Client (Electric Vehicle):**
```python
ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
ctx.verify_mode = ssl.CERT_REQUIRED
ctx.minimum_version = ssl.TLSVersion.TLSv1_2
ctx.maximum_version = ssl.TLSVersion.TLSv1_3
ctx.load_cert_chain("certs/evcc_cert.pem", "certs/evcc_key.pem")
ctx.load_verify_locations("certs/ca.pem")
```

**Negotiated Result:**
- TLS Version: 1.3
- Cipher Suite: TLS_AES_256_GCM_SHA384
- Key Exchange: ECDHE-P256 (classical)
- Authentication: ECDSA-P256 (classical)
- Encryption: AES-256-GCM (quantum-resistant)

---

## 📁 Project Structure

```
pqc_iso15118/
├── main.py                    # Entry point for all 3 components
├── pqc_selftest.py           # Verify PQC installation
├── run_check.py              # Automated system test
├── requirements.txt          # Python dependencies
├── environment.yml           # Conda environment (if needed)
├── README.md                 # This file
├── zz                        # Project memory/architecture notes
│
├── certs/                    # Classical TLS certificates (working)
│   ├── ca.pem               # Certificate Authority
│   ├── secc_cert.pem        # Station certificate
│   ├── secc_key.pem         # Station private key
│   ├── evcc_cert.pem        # Vehicle certificate
│   └── evcc_key.pem         # Vehicle private key
│
├── cloud/
│   └── server.py            # Cloud WebSocket server (port 9000)
│                            # - Certificate verification only
│                            # - Simple JSON messages (no PQC)
│
├── ev_station/
│   ├── server_new.py        # Charging station server (port 15118)
│   │                        # - TLS 1.3 server
│   │                        # - ISO 15118 protocol handler
│   │                        # - Generates own Falcon-512 keys
│   │                        # - Forwards vehicle certs to cloud
│   ├── crypto.py            # PQC crypto implementation
│   │                        # - Falcon-512 sign/verify
│   │                        # - Algorithm negotiation
│   └── v2gtp.py            # V2GTP message framing
│
├── ev_vehicle/
│   └── client_new.py        # Electric vehicle client
│                            # - TLS 1.3 client
│                            # - ISO 15118 5-phase protocol
│                            # - Falcon-512 signatures
│
└── scripts/
    └── gen_certs.sh         # Generate classical ECDSA certs
```

### Component Roles

**Cloud Backend (cloud/server.py):**
- Simple WebSocket server on port 9000
- No PQC or ISO 15118 complexity
- Accepts JSON messages: `{"action": "VerifyVehicleCert", "algo": "...", "cert": "..."}`
- Returns: `{"status": "success", "result": "VERIFIED"}`
- Optional component - system works without it

**Charging Station (ev_station/server_new.py):**
- TLS 1.3 server on port 15118
- Generates own Falcon-512 PQC keys on startup
- Handles full ISO 15118 5-phase protocol
- Forwards vehicle certificates to cloud for verification (if connected)
- Can operate independently without cloud

**Electric Vehicle (ev_vehicle/client_new.py):**
- TLS 1.3 client connecting to station at port 15118
- Executes ISO 15118 protocol flow
- Uses Falcon-512 signatures for all messages
- Measures and reports phase timing

---

## 🧪 Testing & Verification

### Quick Self-Test

```bash
cd /home/rohit-pulagam/Downloads/pqc_iso15118
source niso/bin/activate

# Test PQC installation
python pqc_selftest.py
# Expected: "PQC SELFTEST PASSED: algo=Falcon-512"

# Run automated system test (all 3 components in one process)
python run_check.py
# Expected: "ALL CHECKS PASSED" with full session log
```

### Manual Testing (3 Terminals)

**Complete test with cloud:**
```bash
# Terminal 1 - Cloud
source niso/bin/activate
python main.py --mode cloud --host 0.0.0.0 --port 9000

# Terminal 2 - Station (with cloud connection)
source niso/bin/activate
python main.py --mode station --host 0.0.0.0 --port 15118 \
  --cloud-host localhost --cloud-port 9000 --pqc

# Terminal 3 - Vehicle
source niso/bin/activate
python main.py --mode vehicle --host localhost --port 15118 --pqc
```

**Test without cloud (local-only mode):**
```bash
# Terminal 1 - Station (no cloud)
source niso/bin/activate
python main.py --mode station --host 0.0.0.0 --port 15118 --pqc

# Terminal 2 - Vehicle
source niso/bin/activate
python main.py --mode vehicle --host localhost --port 15118 --pqc
```

### Expected Test Results

**✅ Success Indicators:**
- Vehicle completes all 5 ISO 15118 phases
- Total session time: 570-580ms
- PQC Algorithm: Falcon-512 (not "ECC fallback")
- Negotiated Mode: PQC_ONLY
- TLS Version: TLSv1.3
- Cipher: TLS_AES_256_GCM_SHA384
- Cloud verification: "VERIFIED" (if cloud connected)
- No exceptions or errors in logs

**❌ Common Issues:**

1. **"ECC fallback" in logs:**
   - liboqs-python not installed properly
   - Solution: Re-run liboqs installation steps

2. **Connection refused (port 15118):**
   - Station not running or wrong port
   - Solution: Start station first, verify port 15118

3. **Cloud connection failed:**
   - Normal if cloud not running
   - System works without cloud

4. **TLS handshake error:**
   - Missing/invalid certificates
   - Solution: Run `cd scripts && ./gen_certs.sh`

---

## 🔍 Troubleshooting

### Verify Environment

```bash
# Check Python version (need 3.10+)
python --version

# Check liboqs installation
ls -lh /usr/local/lib/liboqs.*

# Check OQS provider
export OPENSSL_CONF=/usr/lib/ssl/openssl.cnf
openssl list -providers | grep -A3 oqsprovider

# Check Python packages
pip list | grep -E "(cryptography|websockets|liboqs)"

# Test PQC in Python
python -c "import oqs; print('Available:', oqs.get_enabled_sig_mechanisms()[:3])"
```

### Debug Mode

Enable verbose logging:
```bash
# Edit main.py temporarily
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
```

### Check Ports

```bash
# See what's listening
sudo netstat -tlnp | grep -E "9000|15118"

# Kill stuck processes
sudo lsof -ti:15118 | xargs kill -9
sudo lsof -ti:9000 | xargs kill -9
```

---

## 🚧 Known Limitations

### PQC TLS Certificates
- **Issue:** Cannot use ML-DSA/Falcon certificates in TLS handshake
- **Cause:** Python ssl module + liboqs version mismatch + ASN.1 encoding issues
- **Workaround:** Use classical TLS transport + PQC application-layer signatures
- **Impact:** Transport layer is not quantum-safe (but application layer is)

### Cloud Communication
- **Security:** Cloud-Station WebSocket has no encryption
- **Reason:** Local network deployment, focus on Station-Vehicle security
- **Production:** Should add TLS for cloud communication in production

### Performance
- **Falcon-512 vs RSA:** PQC signatures are ~8ms vs <1ms for RSA
- **Acceptable:** 8ms is tolerable for EV charging use case
- **Future:** Could optimize with Falcon-1024 or hardware acceleration

---

## 📚 References

### Standards & Specifications
- **ISO 15118-2:2014** - Vehicle to grid communication interface (V2G)
- **NIST PQC** - Post-Quantum Cryptography standardization
- **TLS 1.3** - RFC 8446

### Libraries & Tools
- **liboqs** - https://github.com/open-quantum-safe/liboqs
- **liboqs-python** - https://github.com/open-quantum-safe/liboqs-python
- **OQS Provider** - https://github.com/open-quantum-safe/oqs-provider
- **OpenSSL 3.x** - https://www.openssl.org/

### PQC Algorithms
- **Falcon** - Fast Fourier lattice-based compact signatures
- **Dilithium (ML-DSA)** - Module-Lattice-Based Digital Signature Algorithm
- **Kyber (ML-KEM)** - Module-Lattice-Based Key Encapsulation Mechanism

---

## 👨‍💻 Development Notes

**Last Updated:** February 12, 2026  
**Python Version:** 3.12.3  
**liboqs Version:** 0.15.0  
**liboqs-python Version:** 0.14.0  
**Architecture:** Simplified (Cloud = verification only, Station = key generation)

**Recent Changes:**
- Simplified cloud-station architecture (no key distribution)
- Station now generates own PQC keys
- Cloud only handles certificate verification via WebSocket
- Updated ports: Cloud=9000, Station=15118
- Added graceful degradation (works without cloud)
- Fixed cloud server run() method for proper infinite loop

**Testing Status:** ✅ All components working, complete sessions in ~575ms

---

## 📄 License

Prototype code for educational and research use. No production guarantees.


## Setup (ECC-only, simplest)
```bash
python3 -m venv ~/.venvs/pqc15118
source ~/.venvs/pqc15118/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Setup (Enable PQC via liboqs)
```bash
# Ubuntu prerequisites
sudo apt-get update
sudo apt-get install -y cmake ninja-build git build-essential libssl-dev

# Use a venv
python3 -m venv ~/.venvs/pqc15118
source ~/.venvs/pqc15118/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Install oqs Python bindings (builds liboqs automatically)
git clone https://github.com/open-quantum-safe/liboqs-python.git
cd liboqs-python
pip install .
```

Verify PQC is active:
```bash
python pqc_selftest.py
# Expect: "PQC SELFTEST PASSED: algo=..."
```

## Run: End-to-End Check
```bash
python run_check.py
# Expect: "ALL CHECKS PASSED"
```

## Run: Components Separately
```bash
# Terminal 1 (Cloud server)
python main.py --mode cloud --host 0.0.0.0 --port 9000

# Terminal 2 (Station / SECC)
python main.py --mode station --host 0.0.0.0 --port 15118 --cloud-host 127.0.0.1 --cloud-port 9000

# Terminal 3 (Vehicle / EVCC)
python main.py --mode vehicle --host 127.0.0.1 --port 15118
```

## Logs
You’ll see logs confirming:
- PQC supported or ECC fallback
- Algorithm selections (SIGN_ALGO, KEM_ALGO, MODE)
- Certificates verified locally + via cloud
- Authorization success
- Meter receipts signed + verified (Cloud)
- Clean session termination

## Project Files
- Main CLI: [main.py](main.py)
- Station server: [ev_station/server.py](ev_station/server.py)
- Crypto abstraction: [ev_station/crypto.py](ev_station/crypto.py)
- V2GTP helpers: [ev_station/v2gtp.py](ev_station/v2gtp.py)
- Vehicle client: [ev_vehicle/client.py](ev_vehicle/client.py)
- Cloud backend: [cloud/server.py](cloud/server.py)
- End-to-end runner: [run_check.py](run_check.py)
- PQC Self-test: [pqc_selftest.py](pqc_selftest.py)
- Deps: [requirements.txt](requirements.txt), optional [environment.yml](environment.yml)

## Troubleshooting
- `ModuleNotFoundError: oqs`: Ensure you installed via `liboqs-python` inside your venv.
- `No matching distribution for pyoqs`: Use `liboqs-python` build path instead of PyPI wheels on some Python versions.
- Port conflicts: Change `--port` values or kill existing processes using 15118/9000.

## License
Prototype code for educational and research use. No production guarantees.
