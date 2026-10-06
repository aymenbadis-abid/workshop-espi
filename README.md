# Sentinel-X

Boîtier de surveillance connecté pour une micro-centrale fictive, isolée et sans personnel.
Menaces couvertes par le sujet : cyberattaques, intrusion physique, risques environnementaux
(fuite de gaz, surchauffe).

Chemin visé : carte NodeMCU (ou simulateur) → MQTTS → FastAPI → PostgreSQL → dashboard Vue.
La caméra du laptop serveur est analysée à part (YOLOv8) et envoie ses alertes à l’API.

Ce dépôt est un squelette. Aucun service n’est encore démarré.

## Réel et simulé

Réel :

- NodeMCU v2 (ESP8266) : WiFi, NTP, TLS, MQTTS
- Lumière : photorésistance + résistance 10 kΩ sur A0
- LED rouge (D5) et LED verte (D6), chacune avec une résistance 220 Ω
- Écran OLED SSD1306 128×64, I2C `0x3C` (SDA = D2, SCL = D1), alimenté en 3,3 V
- Caméra intégrée du laptop qui héberge le serveur

Simulé dans le firmware, voie par voie (`SIMULATE_TEMP`, `SIMULATE_HUM`, `SIMULATE_GAS`) :

- Température, humidité, gaz / fumée
- La détection de personne ne passe pas par la carte : elle est faite par la caméra du serveur

La télémétrie listera les voies simulées dans le champ `simulated`. Le dashboard affichera un badge « simulé » sur ces courbes.

## Arborescence

```
firmware/     PlatformIO (ESP8266). config.h réel ignoré par Git.
api/          FastAPI, architecture router → service → models.
vision/       Détection de personne, processus sur l’hôte (pas dans Docker).
dashboard/    Vue 3.
infra/        Mosquitto, Nginx, scripts de certificats. Aucune clé privée versionnée.
simulator/    Mesures MQTTS de secours, même contrat que la carte.
docs/         Documentation complémentaire.
```

L’adresse IP du laptop n’est jamais codée en dur : firmware dans `config.h`, services dans `.env`.
Le certificat TLS du serveur devra contenir cette IP et pourra être régénéré sans changer l’autorité de certification.

## Démarrage

1. Copier `.env.example` vers `.env` et remplacer les valeurs `change-me`.
2. Ne pas committer `.env`, `config.h`, ni aucune clé privée.

`docker compose up` ne lance encore aucun conteneur : le fichier ne déclare que le projet `sentinel-x` et le réseau `sentinelx`. Mosquitto et PostgreSQL arrivent à l’étape suivante.

## Secrets

Interdits dans Git : mots de passe, identifiants WiFi, `.env`, `config.h`, clés privées (`*.key`, `*.pem`).
Seul le certificat public de l’autorité (`ca.crt`) sera versionné, au moment du firmware.
