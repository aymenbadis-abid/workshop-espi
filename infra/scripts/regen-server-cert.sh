#!/usr/bin/env bash
# Create the Sentinel-X CA once, then renew the MQTT and HTTPS certificates.
# Both certificates include SERVER_IP from .env. Re-running this script keeps
# the same CA, so devices that already trust ca.crt do not need a new one.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CERT_DIR="$ROOT/infra/certs"
ENV_FILE="$ROOT/.env"

if ! command -v openssl >/dev/null 2>&1; then
    echo "openssl is required." >&2
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE. Copy .env.example to .env first." >&2
    exit 1
fi

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

if [[ -z "${SERVER_IP:-}" ]]; then
    echo "SERVER_IP is empty in .env." >&2
    exit 1
fi

if [[ ! "$SERVER_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "SERVER_IP must be an IPv4 address (got: $SERVER_IP)." >&2
    exit 1
fi

mkdir -p "$CERT_DIR"

if [[ -f "$CERT_DIR/ca.crt" && ! -f "$CERT_DIR/ca.key" ]]; then
    echo "ca.crt exists but ca.key is missing. Refusing to create a different CA." >&2
    exit 1
fi

if [[ ! -f "$CERT_DIR/ca.key" ]]; then
    echo "Creating a new CA in $CERT_DIR."
    openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
        -keyout "$CERT_DIR/ca.key" \
        -out "$CERT_DIR/ca.crt" \
        -subj "/CN=Sentinel-X CA"
    chmod 600 "$CERT_DIR/ca.key"
else
    echo "Reusing the existing CA. Only the server certificates will change."
fi

san_config="$(mktemp)"
trap 'rm -f "$san_config"' EXIT

cat >"$san_config" <<EOF
subjectAltName = DNS:mosquitto,DNS:localhost,IP:127.0.0.1,IP:${SERVER_IP}
extendedKeyUsage = serverAuth
keyUsage = digitalSignature,keyEncipherment
basicConstraints = CA:FALSE
EOF

openssl req -newkey rsa:2048 -sha256 -nodes \
    -keyout "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.csr" \
    -subj "/CN=sentinel-x-mqtt"

openssl x509 -req -sha256 -days 825 \
    -in "$CERT_DIR/server.csr" \
    -CA "$CERT_DIR/ca.crt" \
    -CAkey "$CERT_DIR/ca.key" \
    -CAcreateserial \
    -out "$CERT_DIR/server.crt" \
    -extfile "$san_config"

rm -f "$CERT_DIR/server.csr"

openssl req -newkey rsa:2048 -sha256 -nodes \
    -keyout "$CERT_DIR/https.key" \
    -out "$CERT_DIR/https.csr" \
    -subj "/CN=sentinel-x-https"

openssl x509 -req -sha256 -days 825 \
    -in "$CERT_DIR/https.csr" \
    -CA "$CERT_DIR/ca.crt" \
    -CAkey "$CERT_DIR/ca.key" \
    -CAcreateserial \
    -out "$CERT_DIR/https.crt" \
    -extfile "$san_config"

rm -f "$CERT_DIR/https.csr"
# Mosquitto (uid 1883) and Nginx (uid 101) mount this directory read-only.
# 644 lets those users read the keys without a matching host account.
# The keys stay out of Git.
chmod 644 "$CERT_DIR/ca.crt" "$CERT_DIR/server.crt" "$CERT_DIR/server.key" \
    "$CERT_DIR/https.crt" "$CERT_DIR/https.key"
chmod 600 "$CERT_DIR/ca.key"

echo "CA:     $CERT_DIR/ca.crt"
echo "MQTT:   $CERT_DIR/server.crt (SAN IP ${SERVER_IP})"
echo "HTTPS:  $CERT_DIR/https.crt (SAN IP ${SERVER_IP})"
openssl x509 -in "$CERT_DIR/https.crt" -noout -ext subjectAltName
