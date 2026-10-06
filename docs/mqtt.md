# Contrat MQTT Sentinel-X

Le boîtier et le simulateur Python parlent le même JSON. L’API ne fait pas confiance à un autre format. Les identifiants vivent dans `.env`, jamais dans Git.

## Sujets

Base fixe : `sentinelx/g6`.

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

`ts` est un horodatage Unix en secondes. `simulated` liste les voies qui ne viennent pas d’un capteur réel. La lumière est réelle sur la carte (photorésistance sur A0) : elle n’est pas dans `simulated`.

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

- `MQTT_USERNAME` (exemple `esp01`) : publie `telemetry`, `alerts`, `status` ; s’abonne à `cmd`. Le simulateur utilise ce compte.
- `MQTT_API_USERNAME` (exemple `api`) : lit ces trois sujets et publie `cmd`. Il ne publie pas de télémétrie.

Le port de production est **8883** (MQTTS). Le port 1883 n’est pas publié par défaut. Pour l’ouvrir le temps d’un essai : `MQTT_ALLOW_PLAINTEXT=true` dans `.env`, puis :

```bash
docker compose -f docker-compose.yml -f infra/mosquitto/plaintext-ports.yml up -d
```

Sans ces deux conditions, Mosquitto n’écoute pas en clair.

## Certificat et IP du partage de connexion

L’IP du laptop change avec le partage de connexion du téléphone. Elle est lue dans `SERVER_IP` (fichier `.env`). Le script `infra/scripts/regen-server-cert.sh` :

1. crée l’autorité `infra/certs/ca.crt` une seule fois ;
2. régénère seulement le certificat du serveur, avec cette IP dans le SAN, plus `mosquitto`, `localhost` et `127.0.0.1`.

Relancer le script ne remplace pas l’autorité. La carte, qui ne stocke que `ca.crt`, n’a pas à être reflasher pour faire confiance au nouveau certificat serveur.

Fichiers locaux, ignorés par Git : `ca.key`, `server.key`, `server.crt`. Seul `ca.crt` peut être versionné. Le collègue firmware le copiera au moment du flash. Ne pas le déposer dans `firmware/` tant que cette branche n’est pas à lui.

## Essai local

```bash
cp .env.example .env
# Renseigner SERVER_IP avec l'IP du laptop sur le partage de connexion.
./infra/scripts/regen-server-cert.sh
docker compose up -d --build postgres mosquitto
```

PostgreSQL doit accepter une session. Un client MQTTS doit publier sur `sentinelx/g6/telemetry` en présentant `infra/certs/ca.crt`. `git status` ne doit pas montrer de clé privée.
