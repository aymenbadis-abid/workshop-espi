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

// 1 = DHT22 on GPIO 32. 0 = no temperature sensor, temp and humidity stay simulated.
#define USE_DHT 1

// LM393 digital output on GPIO 34. Covering the sensor reads HIGH.
// Set LIGHT_INVERT to 1 if the module marks darkness as LOW.
#define LIGHT_INVERT 0
