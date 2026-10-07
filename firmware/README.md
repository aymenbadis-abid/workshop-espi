# Firmware ESP32

Le sketch v3 d’Abdessamad est intégré ici, avec le MQTTS du serveur. Les broches sont celles de son câblage.

- OLED SSD1306 128×64, I2C `0x3C` : SDA = GPIO 21, SCL = GPIO 22, alimentation 3,3 V
- Lumière : module LM393, sortie numérique sur GPIO 34. Sombre = niveau haut. Si c’est l’inverse sur le module, mettre `LIGHT_INVERT` à 1 dans `config.h`
- DHT22 (température et humidité) : GPIO 32. Sans ce capteur, mettre `USE_DHT` à 0
- LED rouge : GPIO 27, anode via 220 Ω, cathode au GND
- LED verte : GPIO 26, même câblage
- Buzzer : GPIO 25

Le gaz reste simulé : le MQ-2 n’est pas branché. Le bouton « Dérive » du dashboard fait monter ce gaz. La chaleur réelle a deux paliers, ceux d’une salle de serveurs : avertissement dès 27 °C (retour sous 25 °C), danger dès 35 °C (retour sous 33 °C). Le buzzer accélère au palier danger.

## Sujets

| Sujet | Sens | Contenu |
|---|---|---|
| `sentinelx/esp32-01/telemetry` | carte → serveur | JSON toutes les 5 s, plus tout de suite si la lumière ou la chaleur change |
| `sentinelx/esp32-01/status` | carte → serveur | en ligne / hors ligne, retenu, avec IP et uptime |
| `sentinelx/esp32-01/cmd` | serveur → carte | `led_red:1`, `led_green:0`, `buzzer:1`, `auto`, `scenario:drift` |
| `sentinelx/esp32-01/ack` | carte → serveur | `ok:<cmd>` ou `erreur:<cmd>` |
| `sentinelx/esp32-01/alerts` | carte → serveur | sabotage lumière, chaleur, pic de gaz simulé |

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
