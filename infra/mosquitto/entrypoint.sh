#!/bin/sh
# Build the password file from the environment, then run Mosquitto as the
# image user (mosquitto). Private keys and passwords are never written to Git.

set -eu

if [ "$(id -u)" -eq 0 ]; then
    echo "Refusing to run Mosquitto as root." >&2
    exit 1
fi

: "${MQTT_USERNAME:?MQTT_USERNAME is required}"
: "${MQTT_PASSWORD:?MQTT_PASSWORD is required}"
: "${MQTT_API_USERNAME:?MQTT_API_USERNAME is required}"
: "${MQTT_API_PASSWORD:?MQTT_API_PASSWORD is required}"

topic_base="${MQTT_TOPIC_BASE:-sentinelx/g6}"
if [ "$topic_base" != "sentinelx/g6" ]; then
    echo "ACL is fixed to sentinelx/g6 (got MQTT_TOPIC_BASE=$topic_base)." >&2
    exit 1
fi

cp /opt/sentinel/mosquitto.conf /mosquitto/config/mosquitto.conf
cp /opt/sentinel/acl /mosquitto/config/acl
chmod 600 /mosquitto/config/mosquitto.conf /mosquitto/config/acl

plaintext="$(printf '%s' "${MQTT_ALLOW_PLAINTEXT:-false}" | tr '[:upper:]' '[:lower:]')"
case "$plaintext" in
    true|1|yes)
        cat >> /mosquitto/config/mosquitto.conf <<'EOF'

listener 1883
protocol mqtt
allow_anonymous false
password_file /mosquitto/config/passwd
acl_file /mosquitto/config/acl
EOF
        echo "Plaintext MQTT listener enabled on 1883."
        ;;
    *)
        echo "Plaintext MQTT listener disabled."
        ;;
esac

mosquitto_passwd -b -c /mosquitto/config/passwd "$MQTT_USERNAME" "$MQTT_PASSWORD"
mosquitto_passwd -b /mosquitto/config/passwd "$MQTT_API_USERNAME" "$MQTT_API_PASSWORD"
chmod 600 /mosquitto/config/passwd

echo "Starting Mosquitto as user $(id -un) for accounts ${MQTT_USERNAME} and ${MQTT_API_USERNAME}."
exec /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
