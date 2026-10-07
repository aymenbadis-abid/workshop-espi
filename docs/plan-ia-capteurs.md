# Module capteurs : forêt d'isolation

Ce module vit sur le serveur. Il lit les mesures déjà stockées et décide si la forme récente de la température et du gaz sort du normal appris. Il ne commande pas la carte et ne remplace pas les seuils de chaleur du firmware.

## État actuel

L'entraînement ne voit qu'un scénario normal simulé. Dans ce scénario, la température reste autour de 24 °C, avec un petit bruit et un lent va-et-vient. Le pas est de 3 secondes. Le fichier produit est `api/ml_training/models/isolation_forest.joblib`. Le script refuse de l'enregistrer si les fenêtres normales sont trop souvent marquées, ou si une longue dérive simulée passe inaperçue.

Chaque score utilise les 30 dernières paires température–gaz. Le vecteur décrit :

- la pente de la température et la pente du gaz ;
- le niveau moyen de chaque série ;
- l'écart de chaque série ;
- la corrélation entre les deux.

La forêt d'isolation compare cette forme au normal appris. Une fenêtre jugée anormale donne l'alerte « Dérive détectée : température et gaz montent ensemble », au plus une fois toutes les 2 minutes pour un même appareil. Aucune limite fixe du type « température supérieure à 40 °C » n'entre dans ce score.

La carte réelle envoie une mesure toutes les 5 secondes. Le DHT22 fournit la température et l'humidité. Le LM393 fournit la lumière. Le gaz reste simulé, parce que le MQ-2 n'est pas branché. Le champ `simulated` de la télémétrie le dit.

Les seuils locaux sont dans le firmware, avec un retour à la normale décalé pour éviter les bascules :

- avertissement dès 27 °C, effacé sous 25 °C, message « Température élevée : salle serveurs » ;
- danger dès 35 °C, effacé sous 33 °C, message « Température critique : salle serveurs ».

L'obscurité du LM393 publie « Ouverture ou sabotage du boîtier ». Le passage au scénario fuite de gaz publie « Pic de gaz simulé ». Ces trois messages partent de la carte. Le modèle ne les calcule pas.

## Pourquoi l'alerte a été fausse

Le normal appris est une pièce simulée vers 24 °C, au pas de 3 secondes. La salle réelle était vers 26–27 °C, et le gaz publié était une fiction qui continuait de bouger. Le score a mélangé une température vraie et un gaz simulé, puis a utilisé la phrase « montent ensemble » pour toute anomalie de la forêt, même quand les deux pentes ne montaient pas vraiment ensemble.

Trente mesures au pas de 3 secondes couvrent environ 1 min 30. Les mêmes trente mesures au pas de 5 secondes de la carte couvrent environ 2 min 30. La forme apprise et la forme scorée ne durent donc pas le même temps.

## Modèles envisagés

Aucun poids téléchargé ne connaît cette salle. Le recalage se fait sur des mesures de la pièce calme, pas sur un jeu public.

- Forêt d'isolation, déjà dans le projet. On la réentraîne sur le normal de cette salle. C'est le premier choix.
- ECOD, dans la bibliothèque PyOD. Même idée : apprendre seulement le normal, puis marquer ce qui s'en écarte. C'est l'alternative si la forêt d'isolation, une fois recalée, reste trop sensible au bruit de la pièce.
- Chronos-Bolt Tiny (`amazon/chronos-bolt-tiny`), seulement plus tard, et seulement sur une série à la fois. Il sert à voir un saut (une hausse brusque). Il ne sert pas à dire que la température et le gaz montent ensemble.

## Travaux, dans l'ordre

### 1. Ne plus scorer la température réelle avec le gaz simulé

**Problème.** Tant que le MQ-2 n'est pas branché, le gaz n'est pas une mesure de la salle. Le scorer avec la température du DHT22 produit des alertes fausses, comme celle déjà vue vers 26–27 °C.

**Changement.** Si le gaz est marqué simulé, le couple température–gaz n'est pas envoyé à la forêt d'isolation. Les mesures continuent d'être enregistrées et affichées. L'avertissement 27 °C et le danger 35 °C restent ceux de la carte.

**Modèle ou outil.** La forêt d'isolation actuelle reste en place pour le simulateur, où température et gaz sont tous les deux fictifs et cohérents. Elle n'est plus appliquée au mélange réel / simulé de la carte.

**Priorité.** Immédiat. C'est le correctif qui arrête les fausses alertes.

### 2. Recaler le normal sur cette salle

**Problème.** Le normal appris est le scénario simulé vers 24 °C, au pas de 3 secondes. Cette salle est plus chaude, et la carte publie toutes les 5 secondes.

**Changement.** Enregistrer 30 à 60 minutes de salle calme : pas de scénario dérive, pas de fuite, personne qui ne chauffe pas la pièce pour l'essai. Utiliser le pas réel de la carte, 5 secondes. Réentraîner le normal sur ces fenêtres seulement. Vérifier qu'une fenêtre calme tenue à part n'est presque jamais marquée, et qu'une dérive volontaire, plus tard, l'est.

**Modèle ou outil.** Forêt d'isolation, réentraînée sur ces mesures. ECOD (PyOD) seulement si ce recalage ne suffit pas. Les deux s'apprennent sur le normal de la salle. Aucun des deux n'est un modèle pré-entraîné de cette pièce.

**Priorité.** Juste après le point 1, avant de refaire confiance au score sur des mesures réelles.

### 3. Réserver la phrase « montent ensemble »

**Problème.** Aujourd'hui, toute fenêtre rejetée par la forêt reçoit le texte « Dérive détectée : température et gaz montent ensemble ». Une hausse de niveau, un écart plus grand, ou une seule série qui bouge, reçoivent la même phrase.

**Changement.** Garder cette phrase seulement lorsque les deux pentes sont positives et que la corrélation est forte. Une autre anomalie de forme reçoit une phrase qui dit ce qui a bougé, sans prétendre que les deux montent ensemble.

**Modèle ou outil.** Pas de nouveau modèle. Les pentes et la corrélation sont déjà dans le vecteur des 30 mesures. La phrase devient une condition sur ces valeurs, après le score.

**Priorité.** En même temps que le recalage, avant la prochaine démonstration du scénario dérive.

### 4. Laisser 27 °C et 35 °C sur la carte

**Problème.** Un modèle de forme et un seuil de salle serveurs ne répondent pas à la même question. Déplacer 27 °C ou 35 °C dans la forêt d'isolation mélangerait l'alerte locale et l'alerte IA.

**Changement.** Aucun. L'avertissement à 27 °C (retour sous 25 °C) et le danger à 35 °C (retour sous 33 °C) restent dans le firmware. Le modèle continue de décrire la forme de la fenêtre, sans limite fixe de température.

**Modèle ou outil.** Aucun. Ces seuils sont des comparaisons sur la carte.

**Priorité.** À tenir pendant tous les travaux suivants.

### 5. Température et humidité, chacune de son côté

**Problème.** L'humidité du DHT22 est réelle et n'entre pas dans le score. La température réelle, une fois séparée du gaz simulé, n'a plus de modèle à elle. La lumière, elle, a déjà son alerte de sabotage sur la carte.

**Changement.** Plus tard, un score par série réelle : la température d'un côté, l'humidité de l'autre. La lumière n'est pas ajoutée au modèle. L'alerte « Ouverture ou sabotage du boîtier » reste celle du LM393.

**Modèle ou outil.** Forêt d'isolation ou ECOD, recalés sur le calme de chaque série. Chronos-Bolt Tiny seulement ensuite, univarié, pour un saut sur une seule courbe. Il ne remplace pas la phrase « montent ensemble », qui demande deux séries.

**Priorité.** Après le couple température–gaz corrigé. La lumière ne change pas de rôle.

### 6. Couple température–gaz seulement avec un MQ-2 réel

**Problème.** Le couple n'a de sens que si les deux mesures viennent de la salle. Une fuite rapide et une dérive lente ne se voient pas de la même façon : la première est un pic, la seconde est une pente sur la fenêtre.

**Changement.** Quand le MQ-2 sera branché, retirer le gaz de la liste simulée et réapprendre le normal du couple sur la salle calme. La fuite rapide reste un seuil de pic, du même genre que les seuils de chaleur de la carte. La dérive lente reste la fenêtre de 30 mesures. Le pic simulé actuel (« Pic de gaz simulé ») ne devient pas, par magie, une fuite réelle.

**Modèle ou outil.** Forêt d'isolation ou ECOD sur le couple réel, pour la dérive lente. Le pic n'est pas un modèle : c'est un seuil. Chronos-Bolt Tiny peut, plus tard, aider à voir un saut de gaz seul. Il ne décide pas que les deux montent ensemble.

**Priorité.** Seulement après le branchement du MQ-2.

### 7. Aligner la fenêtre sur 5 secondes

**Problème.** La fenêtre compte 30 mesures, sans tenir compte du temps qui les sépare. À 3 secondes, elle dure environ 1 min 30. À 5 secondes, elle dure environ 2 min 30. Scorer la carte avec un modèle appris à 3 secondes compare deux durées différentes.

**Changement.** Apprendre et scorer avec le pas de la carte, 5 secondes. Trente mesures font alors environ 2 min 30, à l'entraînement comme à l'arrivée MQTT. Le simulateur, s'il sert encore à vérifier le modèle, doit utiliser le même pas.

**Modèle ou outil.** Même forêt d'isolation (ou ECOD), réentraînée sur des fenêtres de 30 mesures espacées de 5 secondes. Ce point fait partie du recalage du point 2, pas d'un troisième modèle.

**Priorité.** Avec le recalage sur la salle. Sans cet alignement, le nouveau normal resterait décalé dans le temps.

## Ce qui reste hors du modèle

- Les seuils 27 °C et 35 °C, et leurs retours sous 25 °C et 33 °C.
- L'alerte de sabotage liée à la lumière.
- Le pic de gaz, simulé aujourd'hui, seuil de pic le jour où le MQ-2 sera réel.
- Le dessin du tableau de bord. L'écran devra seulement distinguer mesure réelle, mesure simulée, alerte locale, alerte simulée et alerte IA. Le détail est dans [plan-ia.md](plan-ia.md).
