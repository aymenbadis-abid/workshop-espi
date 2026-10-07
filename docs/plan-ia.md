# Plan des modules d'IA de Sentinel-X

Sentinel-X reste un atelier de surveillance de salle serveurs. Deux intelligences artificielles y travaillent déjà, chacune de son côté. Ce plan les rend fiables en démonstration : faux positifs tenus, alertes qu'on peut expliquer, modèles nommés, mesures de contrôle, et un mode dégradé quand la caméra ou le MQ-2 manque. Il étend le code en place. Il ne le réécrit pas.

La caméra a été testée, une personne a été détectée, puis le service a été arrêté. Rien ici ne demande de le relancer.

## État actuel

### Capteurs

L'entraînement, `api/ml_training/train_isolation_forest.py`, ne voit que le scénario `normal` du simulateur. La température y oscille autour de 24 °C. Le pas est de 3 secondes. Le script construit des fenêtres de 30 paires température–gaz, les normalise, puis ajuste une forêt d'isolation (200 arbres, contamination 0,02). Il refuse d'enregistrer le fichier si plus de 5 % des fenêtres normales tenues à part sont marquées, ou si moins de 80 % d'une longue dérive simulée (scénario lancé vers 15 minutes) le sont. Le fichier est `api/ml_training/models/isolation_forest.joblib`. Il contient le scaler, la forêt et la taille de fenêtre. Il ne contient ni version, ni pas de temps, ni taux de contrôle.

À chaque mesure MQTT, `api/app/mqtt/consumer.py` reprend les 30 dernières lignes de l'appareil et n'en garde que la température et le gaz. `api/app/modules/ml/features.py` en tire sept nombres : pente, moyenne et écart de chaque série, plus la corrélation des deux. `api/app/modules/ml/service.py` répond seulement par oui ou non (`predict` à −1). Le score ignore le champ `simulated`, l'humidité, la lumière et l'écart réel entre les dates. Si le fichier manque, le score est sauté et les mesures continuent.

Une fenêtre refusée devient l'alerte « Dérive détectée : température et gaz montent ensemble », type `anomaly`, source `ml`, au plus une fois toutes les 2 minutes pour un appareil. Le texte est le même quelle que soit la forme. Le détail joint au message ne porte que le nom `isolation_forest`.

Sur la carte, une mesure part toutes les 5 secondes. Trente points couvrent donc environ 2 min 30, alors que l'entraînement, à 3 secondes, couvre environ 1 min 30. Le DHT22 donne la température et l'humidité. Le LM393 donne la lumière. Le MQ-2 n'est pas branché : le gaz est toujours dans `simulated`. Si une lecture DHT échoue, la température ou l'humidité bascule aussi en simulé. Le score a déjà alerté à tort vers 26–27 °C, parce qu'il mélangeait la température vraie et ce gaz fictif.

Les seuils de chaleur sont dans le firmware, avec un retour décalé : avertissement dès 27 °C (effacé sous 25 °C), danger dès 35 °C (effacé sous 33 °C). Les messages sont « Température élevée : salle serveurs », « Température critique : salle serveurs » et « Température revenue à la normale ». L'obscurité stable du LM393 publie « Ouverture ou sabotage du boîtier ». L'entrée dans le scénario fuite publie « Pic de gaz simulé ». Ces alertes partent de la carte, source `mqtt`. Le modèle ne les calcule pas.

Les fichiers `api/app/modules/ml/router.py`, `schemas.py` et `models.py` sont vides. Tout le score passe par le service et le consommateur MQTT.

### Caméra

`vision/main.py` tourne sur le laptop, hors Docker, parce que Docker ne voit pas la caméra. Chaque image est ramenée à 640×480. YOLOv8n (Ultralytics) ne cherche que la classe personne. Le service ne fixe pas de seuil de confiance : la bibliothèque applique le sien, 0,25, et toute boîte renvoyée compte. L'inférence est demandée à la taille 480, plus basse que l'image affichée. Il n'y a ni taille minimale de boîte, ni suivi, ni zone.

Dès qu'une boîte est là, le service poste « Personne détectée devant la caméra ». La source enregistrée est `http`. Un silence de 8 secondes évite la rafale, puis la même personne peut alerter encore. Le départ ne produit rien. Le flux annoté (JPEG qualité 70) est servi en MJPEG sur le port 8090. Le tableau de bord le demande via `/video/stream`. Chaque image lue est analysée. Le temps d'inférence est écrit dans le journal. Les poids `yolov8n.pt` restent hors Git. Une photo peut déjà remplacer la caméra : le service sait boucler sur une image fixe.

### Tableau de bord

Le badge « simulé » est déjà posé sur la température, l'humidité et le gaz d'après la dernière mesure. La lumière est affichée comme réelle, ce qui correspond au LM393. La liste d'alertes montre le type technique (`anomaly`, `person`, `heat`, `tamper`, `gas_leak`), le message, l'heure, puis la source brute (`ml`, `http`, `mqtt`). Le détail du score n'apparaît pas. Les seuils 27 °C et 35 °C ne sont pas dessinés. L'image vidéo pointe toujours vers le flux : caméra arrêtée, l'écran n'a rien à dire.

## Principes

1. La carte décide des limites de salle. L'IA décide d'une forme ou d'une personne. Les deux alertes restent distinctes.
2. Un couple n'est scoré que si, sur les 30 points, la température et le gaz sont de même nature : toutes les deux réelles, ou toutes les deux simulées.
3. Aucun poids public ne connaît cette pièce. Les poids COCO servent à reconnaître une personne. Le normal des capteurs s'apprend sur des mesures de la salle, ou, pour le simulateur, sur son scénario normal.
4. Chaque modèle a une version, le pas et la fenêtre utilisés, et les taux du contrôle. L'alerte cite cette version.
5. Caméra arrêtée ou MQ-2 absent : le reste de la chaîne continue, et l'écran le dit.
6. Le laptop porte déjà Docker. On reste sur des poids nano, et sur small seulement si le nano rate une personne loin. Medium et au-dessus sont trop lourds.
7. On branche les changements sur le consommateur MQTT et sur `vision/main.py`. On ne crée pas un nouveau service.
8. L'IA constate et nomme : personne vue, dérive, mesure hors du normal. Elle ne propose rien à l'admin. Pas de « vous devriez », pas de conseil d'action, pas d'échange qui recommande d'éteindre, d'aérer ou d'appeler. L'admin lit le constat et décide.

## Ce que le visiteur lit sur le tableau de bord

L'écran est le tableau de bord Vue, en français. Quatre courbes : température, humidité, gaz, lumière. À côté : l'état du boîtier, la liste d'alertes, la vidéo, les commandes.

Aujourd'hui, un badge « simulé » apparaît sur la température, l'humidité ou le gaz quand la dernière mesure le dit. La lumière n'a pas de badge : elle est affichée comme réelle. La liste montre un code, la phrase, l'heure, puis un autre code. Le visiteur ne voit pas qui a décidé. La vidéo pointe toujours vers le flux. Caméra arrêtée, le panneau ne le dit pas. Les courbes ne tracent pas 27 °C ni 35 °C. La chaleur de la carte ne se lit que si une alerte est déjà dans la liste, et le nombre 27 ou 35 n'est pas écrit à côté.

Le visiteur doit voir quatre choses sans mode d'emploi.

1. **Mesure réelle ou simulée.** Chaque courbe dit « réelle » ou « simulée ». Le badge « simulé » reste. On écrit aussi « réelle » quand la mesure vient du capteur. Une ligne au-dessus des quatre courbes résume, par exemple : « Température réelle. Humidité réelle. Gaz simulé. Lumière réelle. » La lumière suit le capteur du boîtier. Le gaz reste simulé tant que son capteur n'est pas branché. Si la température ou l'humidité bascule en simulé, la ligne et le badge changent ensemble.

2. **Caméra arrêtée.** Le panneau vidéo écrit « Caméra arrêtée » quand le flux ne répond pas. Le reste de l'écran continue : courbes, alertes, état du boîtier. « Temps réel connecté » en haut parle du lien avec les mesures. L'état de la caméra est la phrase du panneau vidéo.

3. **Décision de la carte.** Dans la liste, le libellé est « Décision de la carte ». La phrase déjà enregistrée reste la phrase principale. Une ligne courte nomme le cas : chaleur, limite 27 °C ; chaleur critique, limite 35 °C ; retour à la normale ; obscurité du boîtier. Les codes de la liste ne sont plus montrés.

4. **Décision de l'IA.** Le libellé est « Décision de l'IA », puis « capteurs » ou « caméra ». La phrase nomme le constat : dérive, mesure hors du normal, personne vue, personne partie. Elle ne dit pas quoi faire. Quand le score commun est en pause, une ligne dit : « Gaz simulé : dérive conjointe inactive ».

**Ordre.** D'abord « Caméra arrêtée », les libellés carte et IA, et le mot réelle ou simulée sur chaque courbe. Ensuite la ligne de résumé au-dessus des courbes. Les traits 27 °C et 35 °C sur la courbe de température viennent en dernier. L'étape 2 les prévoit. Ils ne sont pas dessinés aujourd'hui. Ils rappellent les limites de la carte. Ils ne remplacent pas la phrase d'alerte. La version d'un modèle, si on l'affiche, reste en petit sous la phrase, une fois que l'origine se lit déjà.

Les commandes (scénarios, voyants, buzzer) restent à leur place. Elles n'expliquent pas une alerte.

## Étapes

### 1. Couper le score quand la température et le gaz ne sont pas de même nature

**Priorité.** Immédiate. C'est ce qui arrête les fausses « Dérive détectée ».

**Problème.** Le consommateur envoie toujours les 30 dernières températures et les 30 derniers gaz à la forêt. Sur la carte, la température du DHT22 est réelle et le gaz est simulé. Le normal appris est une pièce fictive vers 24 °C. D'où l'alerte à tort vers 26–27 °C.

**Changement.** Avant le score, lire `simulated` sur la fenêtre. Si une ligne mélange une température réelle et un gaz simulé, ou l'inverse, ne pas appeler la forêt. Les mesures restent enregistrées et dessinées. Le journal dit que la dérive conjointe est en pause parce que le gaz est simulé. Le simulateur, où température et gaz sont tous les deux fictifs, continue d'être scoré avec le modèle actuel. Si le fichier du modèle manque, le comportement déjà en place reste : pas de score, mesures conservées.

**Modèle ou outil.** La forêt d'isolation actuelle. Aucun réentraînement dans cette étape.

**Réussite.** Quinze minutes de salle calme, gaz marqué simulé, température réelle autour de 26–27 °C : aucune alerte `anomaly`. Le scénario dérive du simulateur, lui, finit encore par une alerte. Les messages 27 °C et 35 °C continuent d'arriver avec la source de la carte.

### 2. Rendre l'écran lisible, y compris quand un morceau manque

**Priorité.** Tout de suite après l'étape 1. La démonstration doit se comprendre sans lire `ml` ou `http`.

**Problème.** La liste affiche le type et la source techniques. Le flux vidéo ne dit pas que le service est arrêté. Rien ne sépare le seuil de la carte et le score.

**Changement.** Trois origines en français, à partir de la source et du type déjà stockés :

- carte, pour la chaleur et le sabotage (`mqtt`) ;
- scénario, pour le pic de gaz simulé (`mqtt` et type fuite) ;
- IA capteurs (`ml`) et IA caméra (`http`).

Le message français déjà enregistré reste la phrase principale. À côté, une ligne courte peut donner la version du modèle quand elle existe. Sur les courbes de température, tracer 27 °C et 35 °C comme limites de la carte, à part de toute alerte IA. Si le flux du port 8090 ne répond pas, le panneau vidéo affiche « Caméra arrêtée ». Si la dérive conjointe est en pause, une ligne le dit : « Gaz simulé : dérive conjointe inactive ». Le badge « simulé » déjà présent sur les courbes reste.

**Modèle ou outil.** Aucun. C'est l'affichage des champs déjà renvoyés par l'API.

**Réussite.** Une alerte chaleur se lit « Décision de la carte », une dérive « Décision de l'IA, capteurs », une personne « Décision de l'IA, caméra », un pic de scénario « scénario ». Chaque courbe dit réelle ou simulée. Caméra éteinte, le panneau dit « Caméra arrêtée » et le reste du tableau de bord continue. Cette vérification se fait sans relancer la caméra. Le détail des phrases et l'ordre à l'écran sont dans « Ce que le visiteur lit sur le tableau de bord ».

### 3. Nommer le modèle et garder les taux déjà calculés

**Priorité.** Avant tout réentraînement. Sinon le prochain fichier écrase le précédent sans qu'on sache lequel a alerté.

**Problème.** Le fichier enregistré n'a ni version, ni pas de temps, ni taux. Le script affiche les deux taux puis les oublie. L'alerte ne cite que `isolation_forest`.

**Changement.** À côté de la forêt, écrire une fiche courte : version, date, sur quoi elle a été apprise (simulateur normal, ou salle), pas en secondes, taille de fenêtre, noms des voies, taux de fenêtres normales marquées, taux de dérive tardive marquée. Le script garde ses deux barrières : au plus 5 % sur le normal tenu à part, au moins 80 % sur la dérive tardive. L'alerte emporte la version, le score de la forêt, et les sept nombres de la fenêtre. Les poids YOLO restent hors Git, comme aujourd'hui ; la forêt, petite, peut porter un nom de version dans le dépôt.

**Modèle ou outil.** La même forêt d'isolation. La fiche est un fichier à côté du `.joblib`, pas une plateforme.

**Réussite.** Deux entraînements successifs portent deux versions. Une alerte IA capteurs permet de retrouver le fichier et les deux taux du contrôle qui l'ont autorisé.

### 4. Recaler la température réelle et l'humidité réelle, au pas de la carte

**Priorité.** Après les étapes 1 à 3. C'est le premier modèle qui connaît cette salle.

**Problème.** Le seul normal disponible est le simulateur vers 24 °C, au pas de 3 secondes. La salle réelle est plus chaude, et la carte publie toutes les 5 secondes. Recaler le couple température–gaz sur le flux actuel apprendrait le gaz fictif. Ce couple attend le MQ-2 (étape 12).

**Changement.** Enregistrer 30 à 60 minutes de salle calme : pas de scénario dérive, pas de fuite, personne qui ne chauffe pas la pièce pour l'essai. Deux modèles séparés, un pour la température du DHT22, un pour l'humidité. Fenêtre de 30 mesures au pas de 5 secondes, soit environ 2 min 30, à l'apprentissage comme à l'arrivée MQTT. Si les 30 dates ne couvrent pas à peu près cette durée, le score de cette série est sauté. Garder une part des minutes calmes hors de l'apprentissage. Le couple simulé du scénario normal reste le modèle du simulateur, dans sa propre version, toujours au pas qu'on lui donne pour le contrôle (le même 5 secondes si le simulateur sert encore à la démo de dérive).

La phrase d'une série seule dit ce qui a bougé : niveau, pente ou écart. Elle ne dit pas que la température et le gaz montent ensemble. La lumière n'entre pas dans ces modèles. « Ouverture ou sabotage du boîtier » reste l'alerte du LM393.

**Modèle ou outil.** Forêt d'isolation, une par série, même réglage de contrôle que le script actuel (5 % et 80 %). Le seuil d'alerte est choisi sur les minutes calmes tenues à part, pour que la contamination de 0,02 ne marque pas la salle au repos. ECOD (PyOD) seulement à l'étape 6.

**Réussite.** Sur la part calme tenue à part, moins de 5 % des fenêtres sont marquées. Une hausse lente volontaire de la température, plus tard, est marquée. Trente minutes de salle au repos, vers 26–27 °C, ne produisent pas d'alerte de série. Les seuils 27 °C et 35 °C partent toujours de la carte, y compris pendant cet essai.

### 5. Réserver « montent ensemble » au couple dont les deux pentes montent

**Priorité.** Avec le modèle de couple qui existe déjà pour le simulateur, et de nouveau quand le MQ-2 sera réel.

**Problème.** Toute fenêtre refusée reçoit « Dérive détectée : température et gaz montent ensemble ». Une moyenne plus haute, un écart plus grand, ou une seule série qui bouge, reçoivent la même phrase. Les pentes et la corrélation sont pourtant déjà calculées.

**Changement.** Cette phrase seulement si les deux pentes sont positives et la corrélation forte. Sinon, une phrase qui nomme ce qui a bougé (température, gaz, niveau, écart), sans parler d'une montée commune. Les nombres restent dans le détail de l'alerte, pour qu'on puisse vérifier la phrase.

**Modèle ou outil.** Aucun modèle nouveau. Condition sur les nombres déjà produits, après le score.

**Réussite.** Une fenêtre où seule la moyenne de température sort du normal n'affiche pas « montent ensemble ». Une dérive tardive du simulateur, les deux séries en hausse liées, l'affiche. On peut relire les pentes dans le détail de l'alerte.

### 6. Passer à ECOD seulement si la forêt recalée reste trop nerveuse

**Priorité.** Après l'étape 4, et seulement si le critère des 5 % n'est pas tenu sur la salle calme.

**Problème.** La forêt peut rester sensible au bruit du DHT22 même après recalage. Changer de famille trop tôt mélangerait l'effet du nouveau normal et l'effet du nouvel algorithme.

**Changement.** Réapprendre le même normal, avec les mêmes fenêtres et les mêmes barrières, par ECOD. Garder la forêt si ECOD ne fait pas mieux sur la part calme et sur la hausse volontaire.

**Modèle ou outil.** ECOD, bibliothèque PyOD. Apprentissage sur le normal seulement, comme la forêt. Pas un poids téléchargé de cette salle.

**Réussite.** Sur les mêmes minutes calmes et la même hausse volontaire, ECOD marque moins le repos et marque encore la hausse. Sinon on garde la forêt, et ce résultat est noté dans la fiche du modèle.

### 7. Filtrer la confiance et les petites boîtes

**Priorité.** Premier changement vision. Il se prépare sans ouvrir la caméra : une image fixe suffit pour régler le filtre.

**Problème.** Toute boîte renvoyée alerte. Une détection faible ou une toute petite boîte compte autant qu'une personne proche.

**Changement.** Ne garder que les boîtes dont la confiance atteint environ 0,5, et dont la taille suffit pour une personne dans le cadre filmé. L'alerte ne part que si une boîte passe les deux filtres. Le journal continue d'écrire le temps d'inférence et le nombre de personnes retenues.

**Modèle ou outil.** Le même YOLOv8n. Seuil et taille minimale sont des réglages du service. Les poids restent hors Git.

**Réussite.** Sur une photo de personne proche et nette, la boîte est gardée. Sur une photo sans personne, ou avec une silhouette minuscule, aucune alerte n'est postée. La caméra du laptop reste arrêtée pour cet essai.

### 8. Alerter à l'arrivée, puis au départ

**Priorité.** Après le filtre. Sans boîtes filtrées, le suivi s'accroche aux fausses petites boîtes.

**Problème.** L'alerte part à la première boîte, peut se répéter après 8 secondes, et le départ n'existe pas.

**Changement.** Suivre la même personne d'une image à l'autre. Une alerte à l'arrivée, une alerte au départ. Pas de deuxième arrivée tant que le suivi tient. Le silence de 8 secondes ne remplace plus le suivi. Deux phrases françaises : une pour l'arrivée, une pour le départ. Le tableau de bord les montre telles quelles, avec l'origine « IA caméra ».

**Modèle ou outil.** ByteTrack, déjà disponible avec Ultralytics, branché sur les boîtes filtrées de YOLOv8n. Le détecteur ne change pas.

**Réussite.** Une personne qui entre puis sort produit une arrivée et un départ, dans cet ordre, sans rafale entre les deux. Une personne qui reste dans le champ ne produit qu'une arrivée. Essai sur images ou séquence enregistrée tant que la caméra n'est pas rouverte.

### 9. Analyser quelques images par seconde

**Priorité.** En même temps que le suivi, avant un essai long.

**Problème.** Chaque image lue est analysée. Sur la caméra du laptop, c'est plus de calcul qu'il n'en faut, et le flux du tableau de bord suit cette cadence.

**Changement.** Lancer le détecteur 3 à 5 fois par seconde, à un rythme stable, pour que ByteTrack reste cohérent. Le flux MJPEG du port 8090 peut montrer des images plus souvent que le modèle n'en traite.

**Modèle ou outil.** Aucun. Rythme du service, compatible avec YOLOv8n et ByteTrack.

**Réussite.** Le journal montre une inférence toutes les 200 à 300 ms environ, et le suivi de l'étape 8 tient encore sur une séquence. Le service reste arrêté tant qu'on ne demande pas d'ouvrir la caméra.

### 10. Limiter le cadre à la zone utile

**Priorité.** Quand le filtre et le suivi sont stables. Une zone dessinée trop tôt masquerait un mauvais seuil.

**Problème.** Tout le cadre compte. Un bord de pièce, un reflet ou un passage hors sujet peut lever l'arrivée.

**Changement.** Définir la zone utile (l'entrée surveillée). L'arrivée ne compte que si la boîte est dans cette zone. Le suivi et le départ utilisent la même zone.

**Modèle ou outil.** Supervision, pour la zone. Le détecteur reste celui retenu avant.

**Réussite.** Une personne dans la zone produit l'arrivée. La même personne, hors zone, n'en produit pas. La zone est un réglage du poste, pas un nouvel entraînement.

### 11. Changer de poids seulement si le nano filtré rate une personne loin

**Priorité.** Après les étapes 7 à 10. On ne change pas de fichier tant qu'un cas réel de personne éloignée n'a pas été raté.

**Problème.** De près, YOLOv8n suffit. De loin, la personne devient une petite boîte, surtout après le filtre de taille.

**Changement.** Garder YOLOv8n tant que la personne utile est proche. Si des gens loin manquent encore : essayer YOLO11n, puis YOLO26n, toujours en nano COCO. Passer à la taille small d'un de ces détecteurs seulement si le nano rate encore ces gens loin. Le nom du fichier de poids est celui cité par le service, hors Git.

**Modèle ou outil.** `yolov8n.pt` aujourd'hui. `yolo11n.pt`, `yolo26n.pt`, puis éventuellement la variante small. Poids COCO déjà entraînés. Aucun n'est appris sur les photos de cette salle.

**Réussite.** Sur le cas qui faisait rater le nano, la personne loin est détectée, et le temps d'inférence reste compatible avec 3 à 5 images par seconde à côté de Docker. Si le nano suffit, cette étape s'arrête là, et la fiche le dit.

### 12. Ajouter la pose seulement si un affichage compte comme une personne

**Priorité.** Dernier réglage vision, et seulement si l'essai le montre.

**Problème.** La classe personne de COCO reconnaît une silhouette, y compris sur une affiche ou un écran. Si cet objet est dans la zone et assez grand, les étapes précédentes peuvent encore alerter.

**Changement.** Exiger un squelette plausible avant de compter une arrivée. Une affiche plate ne suffit plus. On n'active pas ce contrôle par précaution.

**Modèle ou outil.** `yolo11n-pose`, poids COCO nano déjà entraîné, hors Git. Il sert de contrôle en plus du détecteur retenu. Il ne remplace pas le suivi.

**Réussite.** L'affiche ou l'écran qui déclenchait l'arrivée ne la déclenche plus. Une personne réelle dans la zone la déclenche encore.

### 13. Chronos-Bolt Tiny, plus tard, sur une seule série

**Priorité.** Après qu'une forêt (ou ECOD) recalée tient le repos de la salle. Chronos ne remplace pas cette forêt.

**Problème.** La fenêtre de 30 points voit une pente. Un saut bref, plus court que la fenêtre, peut rester mou. Chronos-Bolt Tiny est fait pour prévoir une série et voir un écart à cette prévision. Il ne voit pas deux séries à la fois.

**Changement.** L'essayer sur la température seule, puis, si c'est utile, sur l'humidité seule. Comparer au modèle de l'étape 4 sur les mêmes minutes calmes et sur un saut volontaire. L'adopter pour le saut seulement s'il marque le saut sans dépasser 5 % d'alertes sur le repos. La phrase « montent ensemble » ne passe pas par Chronos.

**Modèle ou outil.** `amazon/chronos-bolt-tiny`, déjà entraîné, taille adaptée au CPU du laptop. Une série à la fois.

**Réussite.** Sur la série choisie, le saut volontaire est signalé, et le repos de 30 minutes reste sous la barre des 5 %. Sinon on garde la forêt pour cette série, et la fiche le dit.

### 14. Couple température–gaz le jour où le MQ-2 est branché

**Priorité.** Seulement après le branchement. Jusque-là, l'étape 1 tient.

**Problème.** Le couple n'a de sens que si les deux mesures viennent de la salle. Une fuite rapide est un pic. Une dérive lente est une pente sur environ 2 min 30. Le message actuel « Pic de gaz simulé » est l'entrée dans un scénario, pas une fuite mesurée.

**Changement.** Retirer `gas` de la liste simulée quand la voie est réelle. Réapprendre le normal du couple sur 30 à 60 minutes de salle calme, pas de 5 secondes, fenêtre de 30, avec la fiche de l'étape 3 et la phrase de l'étape 5. La fuite rapide est un seuil de pic, du même genre que 27 °C et 35 °C, décidé à part du modèle de forme. La dérive lente reste la fenêtre. Chronos peut, plus tard, aider à voir un saut de gaz seul. Il ne décide pas que les deux montent ensemble.

**Modèle ou outil.** Forêt d'isolation, ou ECOD si l'étape 6 l'a retenu, réapprise sur le couple réel. Le pic est un seuil, pas un modèle.

**Réussite.** Salle calme avec MQ-2 réel : pas d'alerte de couple au-delà de la barre des 5 %. Une dérive lente des deux voies, pentes positives et corrélation forte, donne « montent ensemble », au plus une fois toutes les 2 minutes. Un pic franc donne l'alerte de seuil, source carte, avec un message qui ne dit plus « simulé ».

## Modèle de langue local, optionnel

Les phrases fixes des étapes précédentes suffisent pour la démonstration. Ce modèle n'est pas une troisième décision. On ne l'ajoute qu'après ces phrases. Son seul rôle : reformuler en une phrase française un fait déjà calculé, une alerte et ses nombres. Si la phrase du code est déjà claire, on ne l'appelle pas.

Il constate. Il ne propose rien. Il ne dit pas d'éteindre, d'aérer ou d'appeler. Il ne cherche pas une cause de lui-même. S'il change un nombre, s'il ajoute un conseil, ou si sa phrase est vide, on garde la phrase fixe.

### Une bibliothèque, un fichier sur le disque

Oui. On peut le charger comme une bibliothèque, dans le programme qui prépare déjà la phrase. Pas OpenAI, pas un service distant, pas une clé.

Deux voies honnêtes :

- **llama-cpp-python.** C'est le choix pour ce laptop. La bibliothèque lit un fichier GGUF posé sur le disque. Aucun réseau au moment de la phrase. Le fichier est quantifié, donc léger à côté de Docker.
- **transformers, avec un petit modèle dans un dossier local.** Les poids sont aussi sur le disque, chargés comme une bibliothèque. La mémoire vive est plus haute : souvent autour d'un gigaoctet pour un demi-milliard de paramètres en précision réduite, et davantage si le fichier n'est pas quantifié. On ne prend cette voie que si le fichier GGUF ne convient pas.

On n'ouvre pas un programme de modèle à côté. On n'envoie pas la phrase dehors.

### Trois tailles, toutes faibles en français

De 135 millions à 0,5 milliard de paramètres, en fichier quantifié. Elles tournent sur le CPU, à côté de Docker. Elles sont faibles en français. Elles peuvent inventer, ou répondre en anglais. On ne montre leur phrase que si elle reprend le fait déjà calculé, sans conseil.

1. **Qwen2.5-0.5B-Instruct, GGUF en Q4.** Environ 0,5 milliard de paramètres, environ 400 Mo sur le disque. Premier essai : à cette taille, c'est le fichier qui a le plus de chances d'écrire une courte phrase en français. Limite : le français reste fragile. Un fait qui n'est pas dans le calcul ne doit jamais apparaître.

2. **SmolLM2-360M, GGUF en Q4.** Environ 360 millions de paramètres, environ 250 Mo. À essayer si l'on veut plus léger. Limite : le français est plus faible, la phrase souvent mal formée. Le frère **SmolLM2-135M** (environ 100 Mo) est encore plus léger et encore moins fiable en français. On ne l'affiche pas au visiteur.

3. **TinyLlama 1.1B, GGUF en Q4, seulement si le 0,5B rate le français.** Environ 1,1 milliard de paramètres, environ 670 Mo. Il dépasse la cible très légère. On ne le charge que si Qwen2.5-0.5B ne tient pas une phrase française correcte sur les alertes déjà écrites. Limite : il est surtout anglais, plus lourd en mémoire, et il invente aussi.

L'appel ne part pas à chaque mesure. Seulement au moment d'une alerte dont on a choisi de reformuler la phrase, et seulement si cette phrase fixe ne suffit pas.

### Mode dégradé

Si le fichier de poids n'est pas sur le disque, l'écran montre la phrase fixe. Pas de message d'erreur. Pas de repli vers un service distant.

## Ce qu'on ne fait pas

- Déplacer 27 °C, 35 °C, ou leurs retours sous 25 °C et 33 °C, dans la forêt ou dans ECOD.
- Mettre la lumière du LM393 dans un modèle. Le sabotage reste l'alerte de la carte.
- Scorer la température réelle avec le gaz simulé, ni apprendre un couple « salle » tant que le MQ-2 n'est pas branché.
- Traiter « Pic de gaz simulé » comme une fuite mesurée.
- Entraîner un détecteur de personnes sur les photos de cette pièce. Les poids COCO filtrés et suivis sont le chemin retenu.
- Télécharger un poids medium ou plus lourd, ni un modèle qui demanderait un GPU.
- Utiliser Chronos-Bolt, même Tiny, pour dire que la température et le gaz montent ensemble.
- Monter une plateforme d'apprentissage, un réentraînement automatique, ou un service d'IA séparé. La fiche à côté du fichier et les taux du script suffisent à cet atelier.
- Réécrire l'API, le firmware ou le tableau de bord. On ajoute le garde-fou de score, la fiche de version, les phrases, et les libellés.
- Relancer la caméra pour appliquer ce plan. On la rouvre seulement quand un essai sur le flux vivant est demandé.
- Demander à l'IA une action. Elle ne dit pas « vous devriez ». Elle ne conseille pas d'éteindre, d'aérer ou d'appeler. Pas d'échange qui recommande. Elle constate et nomme. L'admin décide.
- Appeler un modèle de langue en ligne, OpenAI, un service distant, ou une clé. Si un tel modèle est utilisé, c'est un fichier sur le disque, chargé comme une bibliothèque.
- Laisser ce modèle analyser librement, inventer un nombre, ou proposer une action. S'il reformule, c'est une seule phrase, à partir d'un fait déjà calculé. Si la phrase fixe est déjà claire, on ne l'appelle pas.
- Afficher une erreur quand le fichier de ce modèle manque. La phrase fixe reste à l'écran.
