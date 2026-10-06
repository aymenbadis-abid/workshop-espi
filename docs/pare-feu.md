# Règles de pare-feu

La démo se fait sur le partage de connexion du téléphone (Wi-Fi 2,4 GHz). L’adresse du laptop change : elle est dans `SERVER_IP`, jamais dans le code.

À ouvrir vers le laptop, depuis le téléphone et la carte :

- **TCP 8883** : MQTTS. Seule porte d’entrée de la carte.
- **TCP 443** : dashboard et API en HTTPS, après avoir fait confiance à `infra/certs/ca.crt` dans le navigateur.

À laisser fermés vers le réseau du téléphone :

- **1883** : MQTT en clair. Il n’est pas publié.
- **5432** : PostgreSQL. Il n’est pas publié sur la machine.
- **8000** : API HTTP directe, réservée à la machine (`127.0.0.1`).
- **8080** : dashboard HTTP direct, réservé à la machine.
- **8090** : flux vidéo brut du service Vision. Le dashboard le voit via Docker ; le téléphone n’en a pas besoin.
- **3000, 9090, 8082** : Grafana, Prometheus, journaux. Réservés à `127.0.0.1`.

Exemple avec `ufw`, à adapter si la zone du partage de connexion porte un autre nom :

```bash
sudo ufw default deny incoming
sudo ufw allow 443/tcp
sudo ufw allow 8883/tcp
sudo ufw enable
```

Les conteneurs Mosquitto, PostgreSQL, API, dashboard, Nginx, Prometheus, Grafana et Dozzle tournent sans être root. cAdvisor est l’exception : il lit les cgroups de la machine et le dépôt Docker, qui ne sont lisibles que par root, sinon le CPU et la RAM des conteneurs ne remontent pas.

SSH, s’il est utilisé sur la machine de démo, se fait par clé uniquement. Aucun mot de passe SSH n’est ajouté pour ce projet.

Le certificat HTTPS est signé par la même autorité que MQTT. Changer l’IP du partage de connexion se fait avec `./infra/scripts/regen-server-cert.sh`, sans recréer l’autorité et donc sans reflasher la carte pour la confiance.
