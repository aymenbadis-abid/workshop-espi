# Sentinel-X

Boîtier de surveillance connecté pour une micro-centrale fictive, isolée et sans personnel.
Menaces couvertes par le sujet : cyberattaques, intrusion physique, risques environnementaux
(fuite de gaz, surchauffe).

Chemin visé : carte NodeMCU (ou simulateur) → MQTTS → FastAPI → PostgreSQL → dashboard Vue.
La caméra du laptop serveur est analysée à part (YOLOv8) et envoie ses alertes à l’API.

Le chemin serveur (Mosquitto, PostgreSQL, API, dashboard) se lance avec Docker Compose.
Le firmware de la carte vit à part, dans `firmware/`.

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
Le script `infra/scripts/regen-server-cert.sh` met cette IP dans les certificats MQTT et HTTPS, sans changer l’autorité.

## Installation sur une machine vierge

Prérequis : Docker avec Compose, OpenSSL, Python 3.11.

1. Copier `.env.example` vers `.env`. Remplacer chaque `change-me`. Mettre dans `SERVER_IP` l’adresse du laptop sur le partage de connexion du téléphone (Wi-Fi 2,4 GHz). Cette adresse n’est écrite nulle part dans le code.
2. Générer les certificats : `./infra/scripts/regen-server-cert.sh`. Si l’IP change, relancer le script. L’autorité reste la même : la carte n’a pas à être reflasher pour lui refaire confiance. Seul `ca.crt` est public. Les clés restent sur la machine.
3. Lancer la pile : `docker compose up -d --build`.
4. Faire confiance à `infra/certs/ca.crt` dans le navigateur, puis ouvrir https://127.0.0.1 . Le dashboard HTTP direct reste sur http://127.0.0.1:8080 .
5. Mesures sans la carte :

```bash
python3 -m venv simulator/.venv
simulator/.venv/bin/pip install -r simulator/requirements.txt
simulator/.venv/bin/python simulator/simulate.py
```

6. Détection de personne, sur l’hôte (la caméra n’est pas visible dans Docker) :

```bash
python3 -m venv vision/.venv
vision/.venv/bin/pip install -r vision/requirements.txt
vision/.venv/bin/python vision/main.py
```

`VIDEO_SOURCE=0` utilise la caméra intégrée. Si elle n’est pas là, mettre dans `.env` le chemin d’une vidéo ou d’une photo. Le flux apparaît dans le panneau Vidéo. Une personne crée une alerte.

7. Anomalies : le modèle est déjà entraîné (`api/ml_training/train_isolation_forest.py` le refait sur le scénario `normal`). Le scénario « Dérive » du dashboard doit finir par une alerte. Ce n’est pas un seuil du type `temp > 40`.

8. Carte : le firmware est dans `firmware/` et se flashe à part. Copier `infra/certs/ca.crt` vers la carte au moment du flash. Le contrat MQTT est dans `docs/mqtt.md`.

PostgreSQL n’écoute pas sur le port 5432 de la machine. Session : `docker compose exec postgres psql -U sentinelx -d sentinelx`.

Supervision, en local seulement : Grafana http://127.0.0.1:3000 , Prometheus http://127.0.0.1:9090 , journaux http://127.0.0.1:8082 . Les règles de pare-feu sont dans `docs/pare-feu.md`.

Ne pas committer `.env`, `config.h`, ni aucune clé privée. Le port 1883 n’est pas ouvert.

## Secrets

Interdits dans Git : mots de passe, identifiants WiFi, `.env`, `config.h`, clés privées (`*.key`, `*.pem`).
Seul le certificat public de l’autorité (`infra/certs/ca.crt`) peut être versionné. La carte le recevra au moment du flash ; il n’est pas copié dans `firmware/` par le chemin serveur.
