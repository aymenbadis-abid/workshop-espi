# Firmware ESP32

Le sketch reçu (`sentinel_x.ino`) cible un ESP32, pas le NodeMCU du premier squelette. Les broches ci-dessous sont celles de ce câblage.

- OLED SSD1306 128×64, I2C `0x3C` : SDA = GPIO 21, SCL = GPIO 22, alimentation 3,3 V
- Lumière : GPIO 34 (entrée analogique). En dessous de `LIGHT_DARK_BELOW` (0 à 1023), le boîtier est couvert et une alerte sabotage part. Si couvrir le capteur fait monter la valeur, mettre `LIGHT_INVERT` à 1 dans `config.h`
- LED rouge : GPIO 27, anode via 220 Ω, cathode au GND
- LED verte : GPIO 26, même câblage
- Buzzer : GPIO 25

Température, humidité et gaz sont simulés sur la carte (scénarios `normal`, `drift`, `gas_leak`, `reset`). La lumière ne l’est pas.

## Sujets

| Sujet | Sens | Contenu |
|---|---|---|
| `sentinelx/esp32-01/telemetry` | carte → serveur | JSON toutes les 5 s, plus tout de suite si la lumière change |
| `sentinelx/esp32-01/status` | carte → serveur | en ligne / hors ligne, retenu, avec IP et uptime |
| `sentinelx/esp32-01/cmd` | serveur → carte | `led_red:1`, `led_green:0`, `buzzer:1`, `auto`, `scenario:drift` |
| `sentinelx/esp32-01/ack` | carte → serveur | `ok:<cmd>` ou `erreur:<cmd>` |
| `sentinelx/esp32-01/alerts` | carte → serveur | sabotage lumière, pic de gaz simulé |

Le courtier est en MQTTS sur le port 8883, avec le compte `esp01` du fichier `.env`. Le port 1883 du sketch d’origine ne joint pas ce courtier.

## Compilation

Prérequis : PlatformIO.

```bash
cp firmware/include/config.example.h firmware/include/config.h
```

Renseigner dans `config.h` le Wi-Fi, le mot de passe MQTT, et `MQTT_HOST` avec la même adresse que `SERVER_IP`. Cette adresse doit être dans le certificat du serveur. Si le partage de connexion a changé d’IP :

```bash
# Mettre la nouvelle IP dans .env (SERVER_IP) et dans config.h (MQTT_HOST), puis :
./infra/scripts/regen-server-cert.sh
```

L’autorité ne change pas : `firmware/include/ca_cert.h` reste valable. Ensuite :

```bash
pio run -t upload -d firmware
pio device monitor -d firmware
```

`config.h` et `secrets.h` ne vont pas dans Git.
