# Plan d'écran — démo salle serveurs

Une seule page. Le visiteur lit l'état de la salle en français, d'un coup d'œil. L'écran constate. Il ne propose aucune action à l'admin : pas d'ordre d'aérer, de couper, d'appeler, ni de « vous devriez ».

Règle absolue : une fonctionnalité déjà implémentée apparaît à l'écran. Rien de l'IA ne reste caché derrière un code, un champ ignoré, ou un journal.

## Écran aujourd'hui

Page sombre, deux colonnes, pas de seconde route.

En-tête : « Sentinel-X », puis « Temps réel connecté » ou « Temps réel coupé ». Ce voyant suit seulement la socket des mesures. Il ne dit rien de la carte ni de la caméra.

À gauche, quatre courbes, 60 points, appareil `esp32-01` seulement : température (°C), humidité (%), gaz sans unité, lumière. Courbe vide : « En attente de la carte ESP32 ». Le badge « simulé » suit la liste `simulated` du dernier point, pour la température, l'humidité et le gaz. Le mot « réelle » n'existe pas. La lumière est forcée sans badge, même si le dernier point la marquait simulée. Pas de chiffre courant. Pas de trait à 27 °C ni à 35 °C.

À droite :

- État du boîtier. « En ligne », « Hors ligne », ou « En attente de la carte ». Si un statut `esp32-01` est là : identifiant brut, IP, uptime en secondes. La date de mise à jour du statut est renvoyée et ignorée. Le statut du simulateur (`esp01`) est ignoré.
- Alertes. Les 20 dernières, tous appareils confondus. Titre = code (`anomaly`, `person`, `heat`, `tamper`, `gas`, `gas_leak`, `ack`), puis la phrase française, puis l'heure, puis la source brute (`ml`, `http`, `mqtt`). La couleur suit la sévérité. Le mot information, avertissement ou danger n'est pas écrit. Le modèle joint à la dérive n'est pas lu. L'appareil n'est pas nommé.
- Vidéo. Image sur `/video/stream`. Le nginx du dashboard proxy `/video/` vers le port 8090 de l'hôte, donc `/video/stream` devient `/stream` sur ce port. Le nginx TLS devant ne fait que relayer le site. La caméra est arrêtée : image cassée, aucune phrase. Le serveur de développement Vite ne proxy pas `/video/`.
- Commandes. Scénarios Normal, Dérive, Fuite de gaz, Reset. Voyants rouge et vert. Buzzer : Allumer, Éteindre, Auto. Texte « Envoi… », « Commande envoyée » ou « Échec de la commande ». Un accusé reçu en direct écrase ce texte, et reste aussi dans la liste d'alertes.

Chargement : 60 mesures, 20 alertes, le statut, puis la socket.

## Inventaire

Pour chaque fonctionnalité : ce que le code fait, et ce que l'écran en fait.

### Forêt d'isolation

À chaque mesure conservée, l'API prend les 30 dernières températures et les 30 derniers gaz de cet appareil. Elle calcule sept descripteurs (pentes, moyennes, écarts, lien entre les deux séries) et demande au modèle si la fenêtre est anormale. Pas de seuil fixe ici : 27 °C et 35 °C ne viennent pas de ce modèle. Fichier de modèle absent : aucun score, l'ingestion continue. Fenêtre anormale : alerte « Dérive détectée : température et gaz montent ensemble », sévérité avertissement, au plus une fois toutes les 2 minutes par appareil. Le détail stocké est le nom du modèle. Les sept nombres et le score numérique ne sont pas enregistrés. Le score ne regarde pas si la voie est simulée : une dérive de scénario peut donc produire cette alerte.

Écran aujourd'hui : la phrase française apparaît dans la liste, noyée, avec le code `anomaly` et la source `ml`. Le nom du modèle est dans la réponse et ignoré. Les sept nombres sont calculés puis jetés. La décision n'a pas de place fixe : elle disparaît dès qu'elle sort des 20 dernières lignes.

### Alerte personne, YOLOv8n

Le service vision, sur l'hôte, redimensionne l'image, ne garde que la classe personne, dessine les cadres, et sert le flux annoté en MJPEG sur le port 8090, chemins `/stream` et `/`. Dès qu'au moins une personne est vue, il poste « Personne détectée devant la caméra », appareil caméra, sévérité avertissement, au plus une fois toutes les 8 secondes. Le départ d'une personne ne publie rien. Le nom du modèle, le nombre de personnes et le temps de calcul restent dans le journal du processus. L'alerte stockée n'a pas de détail de modèle. La source enregistrée vaut `http`.

Écran aujourd'hui : la phrase arrive dans la même liste, titre `person`, source `http`. Le nom YOLOv8n n'est écrit nulle part. Le flux est branché en permanence ; caméra arrêtée, l'image est cassée. Le nombre de personnes et la latence sont calculés puis jetés.

### Chaleur, 27 °C et 35 °C

La carte décide sur la température du DHT22. Avertissement dès 27 °C, effacé sous 25 °C. Danger dès 35 °C, effacé sous 33 °C. Elle publie « Température élevée : salle serveurs », « Température critique : salle serveurs », ou « Température revenue à la normale ». Chaque mesure emporte aussi `alert_heat` : 0 normale, 1 avertissement, 2 danger. Une lecture DHT ratée ne change pas ce niveau. La courbe peut alors afficher la température de scénario pendant que la décision carte reste celle du dernier DHT valide.

Écran aujourd'hui : la phrase d'alerte est dans la liste, titre `heat`, source `mqtt`, sans les seuils. `alert_heat` est calculé par la carte puis jeté par l'API avant la base et avant la socket. Pas de trait à 27 ni à 35. Pas d'état chaleur courant en dehors de la liste.

### Sabotage lumière

Le module lumière est réel. Sombre stable : valeur 80, alerte « Ouverture ou sabotage du boîtier », avertissement. Claire : 640. Le retour à la lumière ne publie pas d'alerte. `light_dark` et `transitions_1min` partent avec la mesure. Ce n'est pas des lux. La lumière n'entre pas dans la liste `simulated` du firmware.

Écran aujourd'hui : la courbe montre 80 ou 640, sans « Claire » ni « Sombre », et le badge simulé est interdit par le code de la page. L'alerte est dans la liste, titre `tamper`. `light_dark` et le compte de bascules sont calculés puis jetés par l'API. L'état sombre en cours n'a pas de place fixe.

### Gaz MQ

Le firmware du commit `7eda3be` lit le MQ (broche analogique, préchauffage 60 s dans l'air propre, puis cette moyenne devient la référence). Ensuite `gas` est la valeur lissée, échelle analogique, pas des ppm. `gas_raw` est cette lecture. `gas_delta` est l'écart à la référence, vide pendant le préchauffage. `gas_ready` vaut 1 quand la référence existe, sinon 0. Alerte carte à +400, effacement à +250. `alert_gas` vaut 1 ou 0. Phrases : « Gaz élevé », « Gaz revenu à la normale ». Pendant le préchauffage, ou sans MQ, `gas` dessiné reste le scénario et `gas` est dans `simulated`.

Écran aujourd'hui : une courbe « Gaz » et, au mieux, le badge « simulé » du dernier point. `gas_raw`, `gas_delta`, `gas_ready` et `alert_gas` sont envoyés par la carte puis jetés par l'API. Le tableau de bord ne montre ni `gas_ready` ni `alert_gas`. Les phrases « Gaz élevé » et « Gaz revenu » n'apparaissent que si elles sont encore dans les 20 alertes, sous le code `gas`.

### Scénarios

Normal, dérive, fuite, reset. Ils remplissent seulement les voies encore simulées. Un DHT qui répond et un MQ prêt ne sont pas remplacés. Entrer en fuite publie quand même « Pic de gaz simulé », critique, même si la courbe de gaz est réelle. Le simulateur Python (`esp01`) fait la même alerte. Ses courbes ne s'affichent pas. Ses alertes, oui.

Écran aujourd'hui : quatre boutons. L'alerte de fuite est dans la liste, titre `gas_leak`. Rien n'écrit que le scénario ne touche pas une voie réelle, ni quel scénario est en cours.

### Accusés

La carte répond `ok:` ou `erreur:`. L'API en fait une alerte de type `ack`, phrases « Commande acceptée » ou « Commande refusée », et la phrase garde la commande brute. Le buzzer est accepté puis la carte force la broche à l'arrêt : aucun son. `auto` rend les voyants à la carte (obscurité, chaleur ou gaz). `gas_cal` recale la référence sur la carte ; l'API de commandes le refuse.

Écran aujourd'hui : chaque accusé est une alerte de salle. En direct, le même texte remplace aussi le message sous les boutons. Au chargement, les anciens accusés restent seulement dans la liste.

### Statut

En ligne, hors ligne (y compris le testament), IP, uptime, date de mise à jour. La mesure emporte aussi `manual` (un voyant ou le buzzer est forcé) et `rssi`. L'écran ne garde que `esp32-01`.

Écran aujourd'hui : en ligne ou hors ligne, identifiant, IP, uptime en secondes. La date est renvoyée et ignorée. `manual` et `rssi` sont calculés puis jetés par l'API. Sans statut : « En attente de la carte » et « En attente de la carte ESP32. »

## Lecture voulue

Quatre réponses, sans ouvrir une liste :

1. Voie réelle ou simulée.
2. Décision de la carte : chaleur, gaz, lumière.
3. Décision de l'IA : dérive (forêt d'isolation), personne (YOLOv8n).
4. Caméra arrêtée, ou le flux.

Hiérarchie : bandeau, puis le chiffre de chaque mesure, puis la courbe, puis les constats, puis la vidéo, puis les commandes en retrait. Français partout. Aucun code `ml`, `http`, `mqtt`, ni aucun type brut, en titre.

## Étapes

### 1. Faire arriver à l'écran ce que la carte calcule déjà

**Problème.** `gas_raw`, `gas_delta`, `gas_ready`, `alert_gas`, `alert_heat`, `light_dark`, `transitions_1min`, `manual` et `rssi` partent du firmware et s'arrêtent à la validation de l'API. L'écran ne peut pas les montrer.

**Changement.** L'API conserve ces champs et les renvoie avec chaque mesure, historique et socket. Champ absent sur un ancien message : l'écran écrit « non reçu ». Il n'invente pas un préchauffage ni un niveau de chaleur.

**Priorité.** Bloquante. Sans elle, le gaz réel et les décisions carte restent cachés.

**Comment on vérifie.** Une mesure du boîtier reçue par la page contient `gas_ready` et `alert_gas`. Un message ancien, sans ces clés, affiche « non reçu » à la place d'un chiffre fabriqué.

### 2. Bandeau de lecture immédiate

**Problème.** L'état utile est dispersé : socket en haut, carte en secondes brutes, chaleur et gaz seulement s'ils sont encore dans la liste, caméra muette, IA illisible.

**Changement.** Une bande sous le titre.

- Carte : en ligne, hors ligne, ou en attente. IP, temps depuis le démarrage en minutes, « vu à » depuis la date de statut. Signal Wi-Fi si `rssi` est là, sinon « non reçu ».
- Mode : auto, ou manuel si `manual` vaut 1.
- Décision carte : chaleur (normale, avertissement, danger), gaz (normal ou élevé d'après `alert_gas`), lumière (claire ou sombre). Chaque pastille absente dit « non reçu ».
- Décision IA : le dernier constat de dérive, avec « forêt d'isolation », et le dernier constat personne, avec « YOLOv8n ». Aucun constat encore : « Aucune dérive signalée » et « Aucune personne signalée ». Ce sont des constats, pas des conseils.
- Caméra : « Caméra arrêtée », ou « Flux en cours ».

Le voyant du haut parle de la liaison des mesures, avec ces mots, pour ne plus le confondre avec la carte ou la caméra.

**Priorité.** Immédiate pour la démo. Les pastilles carte et gaz s'appuient sur l'étape 1. Les pastilles IA s'appuient sur les alertes déjà reçues.

**Comment on vérifie.** À un mètre, on répond aux quatre questions sans lire le code source de la page. Socket coupée : la liaison des mesures le dit, et la caméra garde son propre mot. Carte absente : « En attente de la carte ESP32 » reste visible.

### 3. Quatre mesures, chiffre puis courbe

**Problème.** Pas de valeur courante. « Simulé » n'a pas de contraire. La lumière est affichée sans mot, par force. Les courbes des autres appareils sont déjà exclues, et ça doit le rester.

**Changement.** Sur chaque carte : dernier nombre, unité, puis « réelle » ou « simulée » selon la liste du dernier point pour cette voie. Température en °C, humidité en %. La lumière du boîtier, absente de cette liste, est « réelle ». La courbe reste dessous, 60 points, `esp32-01` seulement. File vide : « En attente de la carte ESP32 ».

**Priorité.** Immédiate. Ces champs sont déjà dans la mesure.

**Comment on vérifie.** Dernier point avec `gas` dans `simulated` : badge simulé sur le gaz, et « réelle » sur une voie absente de la liste. Lumière : le mot « réelle », jamais un badge simulé forcé à vide. Une mesure `esp01` ne trace rien. Zéro point `esp32-01` : la phrase d'attente, pas un graphique vide.

### 4. Traits de chaleur sur la température

**Problème.** 27 °C et 35 °C sont les paliers de la carte. Le graphique ne les montre pas.

**Changement.** Deux traits horizontaux : 27 °C avertissement, 35 °C danger. Légende : limites de la carte. À côté, les retours : effacement sous 25 °C et sous 33 °C. La pastille chaleur suit `alert_heat`, pas un recalcul sur la courbe. Courbe simulée et `alert_heat` à 0 : la pastille reste « normale », les traits restent des limites de carte.

**Priorité.** Immédiate pour les traits. La pastille fidèle attend l'étape 1.

**Comment on vérifie.** Les deux traits sont visibles sur la température. Une série simulée au-dessus de 35 °C avec `alert_heat` à 0 ne passe pas la pastille en danger.

### 5. Gaz : réel, préchauffage, ou simulé

**Problème.** Une seule courbe. Le MQ prêt (commit `7eda3be`) ne se distingue pas du scénario. `gas_ready` et `alert_gas` n'atteignent pas la page.

**Changement.** Un seul état à la fois, dès que les clés sont là.

- Réel : `gas_ready` à 1 et gaz absent de `simulated`. Nombre lissé, écart `gas_delta`, unité « compte analogique ». Phrase de constat : alerte carte à +400, retour à +250. Pastille élevée si `alert_gas` vaut 1.
- Préchauffage : `gas_ready` à 0 et `gas_raw` est un nombre. « Préchauffage, 60 s », la lecture capteur, et en petit le `gas` de scénario marqué scénario.
- Simulé : gaz dans `simulated` et `gas_raw` vide. Badge simulé. Pas de phrase de préchauffage, pas de +400.

Clés absentes : « réelle » ou « simulée » d'après la liste, plus « détail gaz non reçu ».

**Priorité.** Juste après l'étape 1.

**Comment on vérifie.** Avant 60 s : préchauffage et lecture brute, le scénario n'est pas présenté comme le MQ. Après la référence : écart et pastille selon `alert_gas`. Sans capteur : simulé, sans faux préchauffage.

### 6. Constats en français, origine nommée

**Problème.** La liste montre le code, puis la phrase, puis `ml`, `http` ou `mqtt`. On ne sait pas qui a décidé. Le nom « forêt d'isolation » est ignoré. YOLOv8n n'est écrit nulle part.

**Changement.** La phrase stockée reste le constat. Au-dessus, l'origine en français :

- décision de la carte, pour la chaleur, le gaz du MQ, le sabotage ;
- scénario, pour « Pic de gaz simulé » ;
- décision de l'IA, capteurs, pour la dérive, avec « Modèle : forêt d'isolation » lu dans le détail déjà stocké ;
- décision de l'IA, caméra, pour la personne, avec « YOLOv8n ».

Sévérité en mots : information, avertissement, danger. La couleur actuelle reste. Appareil nommé : boîtier, caméra, ou simulateur pour `esp01`. Les accusés quittent cette liste (étape 9). Aucune phrase nouvelle du type conseil.

Le bandeau IA reprend le dernier constat de chaque famille, pour qu'il reste lisible quand la liste défile. Pas de score inventé, pas des sept nombres : ils ne sont pas gardés.

**Priorité.** Immédiate. Phrase, sévérité, origine, appareil et nom du modèle capteurs sont déjà renvoyés. Le libellé YOLOv8n est l'identité du service, écrite sur le panneau, pas un champ manquant.

**Comment on vérifie.** La liste et le bandeau ne contiennent ni `ml`, ni `http`, ni `mqtt`, ni `anomaly`, ni `person`. Une dérive affiche « forêt d'isolation ». Une personne affiche « YOLOv8n » et la phrase déjà stockée. Aucune ligne ne dit quoi faire.

### 7. Caméra arrêtée, ou le flux

**Problème.** L'image pointe toujours vers `/video/stream`. Service arrêté, image cassée. Le voyant du haut peut quand même dire que les mesures sont reliées.

**Changement.** Le panneau interroge la même adresse, celle que le nginx envoie au port 8090. Pas de flux : la phrase « Caméra arrêtée », pas d'image cassée. Flux là : l'image annotée, légende « YOLOv8n, personne ». Un contrôle lent reprend le flux si le service démarre plus tard. L'écran ne lance pas la caméra. Le reste de la page continue.

**Priorité.** Immédiate.

**Comment on vérifie.** Caméra arrêtée : la phrase, pas d'icône cassée, courbes et constats toujours là. On ne démarre pas le service pour cette vérification. Le chemin reste `/video/stream`.

### 8. Lumière en claire ou sombre

**Problème.** La courbe saute entre 80 et 640 sans le dire. Le compte de bascules est jeté. Le sabotage n'est visible que dans la liste.

**Changement.** Valeur courante : « Claire » pour 640, « Sombre » pour 80. La courbe reste la trace de ces deux niveaux. Si `transitions_1min` arrive : « N changements sur 1 min ». Sinon : « compte non reçu ». `light_dark` à 1 : la pastille carte reprend le constat « Ouverture ou sabotage du boîtier ». Le retour au clair met la pastille à « Claire » sans inventer une alerte de fin : le firmware n'en publie pas.

**Priorité.** Avec le bandeau, dès que l'étape 1 a livré les champs. Le mot claire ou sombre se déduit déjà du nombre affiché.

**Comment on vérifie.** 640 affiche Claire, 80 affiche Sombre. Badge lumière : « réelle ». Une alerte sabotage dans la liste porte l'origine carte. Champ de bascules absent : « compte non reçu ».

### 9. Scénarios, accusés, commandes

**Problème.** « Fuite de gaz » a l'air de piloter le MQ. « Dérive » a l'air de tordre un capteur réel. Le buzzer a l'air de sonner. Les accusés se mélangent aux constats de la salle, et leur texte montre encore la commande brute.

**Changement.** Sous les scénarios : ils ne remplissent que les voies marquées simulées. Un MQ prêt ne suit pas la fuite. Le bouton fuite publie tout de même le constat « Pic de gaz simulé », classé scénario. Sous le buzzer : la commande part, et le firmware actuel laisse la broche à l'arrêt. Les boutons restent. À côté des voyants, le dernier accusé en français : voyant rouge allumé, voyant vert éteint, commande refusée, mode auto. Les accusés ne sont plus des alertes de salle. Une ligne, sans bouton : recaler la référence gaz se fait sur la carte. Cet écran ne l'envoie pas, l'API ne l'accepte pas.

**Priorité.** Avec l'étape 6.

**Comment on vérifie.** Après un accusé, la liste des constats n'a plus cette ligne ; le bloc commandes l'a, en français, sans `led_red` ni `scenario:`. Fuite avec gaz réel : la courbe réelle ne devient pas le pic, et le constat de scénario est quand même là. Le buzzer n'est pas présenté comme une sirène qui sonne.

### 10. Hiérarchie visuelle

**Problème.** Tout a le même poids : courbes, alertes, image cassée, boutons.

**Changement.** Le bandeau domine. Les chiffres des mesures passent avant les courbes. Les constats passent avant les commandes. Les commandes sont un bloc secondaire, libellé comme commandes de démonstration. La vidéo a la taille du flux, ou la phrase « Caméra arrêtée » à la même place. Français, contrastes déjà présents (normal, avertissement, danger) gardés et doublés par le mot.

**Priorité.** En même temps que les étapes 2 à 7, pour que la démo soit lisible au premier écran.

**Comment on vérifie.** Sans lire les boutons, on voit la carte, la décision carte, la décision IA et la caméra. Les commandes ne sont pas le premier bloc.

## Hors de cet écran

Pas de ppm, pas de lux, pas de jauge de confiance, pas des sept nombres, pas un score fabriqué. Pas de second écran pour `esp01` : s'il est seul, les courbes restent vides et la phrase dit que le boîtier attendu n'a rien publié. Ses constats, s'ils arrivent, portent le mot simulateur.

Pas de bouton pour lancer la caméra. Pas de bouton pour recaler le gaz. Pas d'écran de connexion. Pas de conseil de l'IA.
