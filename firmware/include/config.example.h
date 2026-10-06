#pragma once

// Copy this file to config.h in the same directory and fill the real values.
// config.h is gitignored. Do not commit Wi-Fi or MQTT passwords.

#define WIFI_SSID "change-me"
#define WIFI_PASS "change-me"

// Laptop address on the phone hotspot (2.4 GHz). Never commit a real address
// that you do not want in the example; the running copy lives in config.h.
#define MQTT_HOST "192.168.0.10"
#define MQTT_PORT 8883
#define MQTT_USER "esp01"
#define MQTT_PASS "change-me"

#define DEVICE_ID "esp32-01"

// Light is scaled to 0..1023. A reading below this means the box is covered.
// Set LIGHT_INVERT to 1 if covering the sensor makes the raw value rise.
#define LIGHT_DARK_BELOW 250
#define LIGHT_INVERT 0
