# Firmware

PlatformIO, carte NodeMCU v2 (ESP8266), C++ / Arduino.

Le code applicatif n’est pas encore écrit. Broches prévues, toutes dans `pins.h` le moment venu :

- OLED SSD1306 128×64, I2C `0x3C` : SDA = D2, SCL = D1, alimentation 3,3 V
- Lumière : photorésistance + 10 kΩ sur A0 (`3V3 — LDR — A0 — 10 kΩ — GND`)
- LED rouge : D5, anode via 220 Ω, cathode au GND
- LED verte : D6, même câblage

Ne pas utiliser D3, D4 ni D8 (broches sensibles au démarrage). A0 ne doit jamais recevoir du 5 V.

`config.h` (WiFi, IP du serveur, identifiants MQTT) est ignoré par Git. Un `config.example.h` sera ajouté avec le firmware. Seul `certs/ca.crt` (certificat public) sera versionné.
