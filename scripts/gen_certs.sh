#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")"/.. && pwd)
CERT_DIR="$ROOT_DIR/certs"
mkdir -p "$CERT_DIR"

# Generate CA key and certificate
if [[ ! -f "$CERT_DIR/ca.pem" ]]; then
  openssl req -x509 -newkey rsa:4096 -days 3650 -nodes \
    -keyout "$CERT_DIR/ca.key" -out "$CERT_DIR/ca.pem" \
    -subj "/CN=PQC-ISO15118-CA"
fi

# Function to issue a cert signed by CA
issue_cert() {
  local name=$1
  local cn=$2
  openssl req -new -newkey rsa:3072 -nodes -keyout "$CERT_DIR/${name}_key.pem" -out "$CERT_DIR/${name}.csr" \
    -subj "/CN=${cn}"
  openssl x509 -req -in "$CERT_DIR/${name}.csr" -CA "$CERT_DIR/ca.pem" -CAkey "$CERT_DIR/ca.key" -CAcreateserial \
    -out "$CERT_DIR/${name}_cert.pem" -days 365 -sha256
}

# Issue SECC and EVCC certs
issue_cert secc SECC-001
issue_cert evcc EVCC-001

# Print summary
ls -l "$CERT_DIR"
echo "Certificates generated in $CERT_DIR"
