# Contrat MQTT Sentinel-X

Le simulateur Python parle le JSON ci-dessous. La carte ESP32 publie le même JSON de mesures, et reçoit ses commandes en texte simple. Les identifiants vivent dans `.env`, jamais dans Git.

## Sujets

Deux bases. Le simulateur Python reste sur `sentinelx/g6`. La carte ESP32 utilise `sentinelx/esp32-01` (compte MQTT `esp01`, comme le simulateur).

| Sujet | Direction | Rôle |
|---|---|---|
| `sentinelx/esp32-01/telemetry` | carte → serveur | mesures, toutes les 5 s, et tout de suite si la lumière change |
| `sentinelx/esp32-01/status` | carte → serveur | `online` / `offline`, message retenu, IP et uptime |
| `sentinelx/esp32-01/cmd` | serveur → carte | texte : `led_red:1`, `led_green:0`, `buzzer:0`, `auto`, `scenario:drift` |
| `sentinelx/esp32-01/ack` | carte → serveur | `ok:<cmd>` ou `erreur:<cmd>` |
| `sentinelx/esp32-01/alerts` | carte → serveur | sabotage lumière, pic de gaz |

Le dashboard envoie ces textes. Les LED et les scénarios sont aussi publiés en JSON sur `sentinelx/g6/cmd`, pour le simulateur.

Base du simulateur : `sentinelx/g6`.

| Sujet | Direction | Rôle |
|---|---|---|
| `sentinelx/g6/telemetry` | carte → serveur | mesures, toutes les 2 à 5 s |
| `sentinelx/g6/alerts` | carte → serveur | événement immédiat (ex. sabotage lumière) |
| `sentinelx/g6/status` | carte → serveur | présence, IP, uptime ; testament MQTT (Last Will) |
| `sentinelx/g6/cmd` | serveur → carte | LEDs et scénarios |

## Télémétrie

```json
{
  "device": "esp01",
  "ts": 1760000000,
  "temp": 24.5,
  "hum": 48,
  "gas": 312,
  "light": 640,
  "simulated": ["temp", "hum", "gas"]
}
```

`ts` est un horodatage Unix en secondes. `simulated` liste les voies qui ne viennent pas d’un capteur réel. La lumière est réelle sur la carte (GPIO 34) : elle n’est pas dans `simulated`. Un ancien message qui n’a que `light_dark` est encore accepté.

## Alerte

```json
{
  "device": "esp01",
  "ts": 1760000000,
  "type": "tamper",
  "message": "Ouverture ou sabotage du boîtier",
  "severity": "warning"
}
```

`severity` vaut `info`, `warning` ou `critical`.

## État

```json
{
  "device": "esp01",
  "online": true,
  "ip": "192.168.43.21",
  "uptime": 3600
}
```

Le testament MQTT publie le même objet avec `"online": false`, en message retenu (retain), pour que le serveur voie la coupure.

## Commandes

Vers la carte, le texte exact est `led_red:1`, `led_green:0`, `buzzer:1`, `buzzer:0` ou `auto`. Un scénario part comme `scenario:normal`, `scenario:drift`, `scenario:gas_leak` ou `scenario:reset`. La carte répond `ok:` ou `erreur:` suivi de la commande.

Le simulateur, lui, reçoit le JSON suivant sur `sentinelx/g6/cmd`.

LED :

```json
{"target": "led_red", "state": "on"}
```

`target` : `led_red` ou `led_green`. `state` : `on` ou `off`.

Scénario de simulation :

```json
{"scenario": "drift"}
```

Valeurs : `normal`, `drift`, `gas_leak`, `reset`.

- `normal` : valeur de base, bruit, cycle lent.
- `drift` : la température monte lentement et le gaz monte un peu. C’est le cas prévu pour l’Isolation Forest.
- `gas_leak` : pic brutal de gaz.
- `reset` : retour aux valeurs de base.

## Comptes et ACL

Deux comptes, créés au démarrage de Mosquitto à partir de `.env` :

- `MQTT_USERNAME` (exemple `esp01`) : publie télémétrie, alertes, statut et ack ; s’abonne aux commandes. Le simulateur et la carte utilisent ce compte.
- `MQTT_API_USERNAME` (exemple `api`) : lit ces sujets et publie les commandes. Il ne publie pas de télémétrie.

Le port de production est **8883** (MQTTS). Le port 1883 n’est pas publié par défaut. Pour l’ouvrir le temps d’un essai : `MQTT_ALLOW_PLAINTEXT=true` dans `.env`, puis :

```bash
docker compose -f docker-compose.yml -f infra/mosquitto/plaintext-ports.yml up -d
```

Sans ces deux conditions, Mosquitto n’écoute pas en clair.

## Certificat et IP du partage de connexion

L’IP du laptop change avec le partage de connexion du téléphone. Elle est lue dans `SERVER_IP` (fichier `.env`). Le script `infra/scripts/regen-server-cert.sh` :

1. crée l’autorité `infra/certs/ca.crt` une seule fois ;
2. régénère seulement le certificat du serveur, avec cette IP dans le SAN, plus `mosquitto`, `localhost` et `127.0.0.1`.

Relancer le script ne remplace pas l’autorité. La carte embarque cette autorité dans `firmware/include/ca_cert.h`. Un nouveau certificat serveur, signé par la même autorité, ne demande pas de recompiler la carte. L’adresse dans `config.h` (`MQTT_HOST`) doit être celle du SAN, donc la même que `SERVER_IP`.

Fichiers locaux, ignorés par Git : `ca.key`, `server.key`, `server.crt`, `firmware/include/config.h`. Seul `ca.crt` (et sa copie dans le firmware) peut être versionné.

## Essai local

```bash
cp .env.example .env
# Renseigner SERVER_IP avec l'IP du laptop sur le partage de connexion.
./infra/scripts/regen-server-cert.sh
docker compose up -d --build postgres mosquitto
```

PostgreSQL doit accepter une session. Un client MQTTS doit publier sur `sentinelx/g6/telemetry` en présentant `infra/certs/ca.crt`. `git status` ne doit pas montrer de clé privée.
