# Module caméra : YOLOv8n

Ce module tourne sur le laptop, dans `vision/main.py`, hors Docker. Docker ne voit pas la caméra intégrée. Le processus ramène chaque image à 640×480, cherche une personne, poste une alerte à l'API, et sert un flux MJPEG.

La caméra a été testée : une personne a bien été détectée. Le service a ensuite été arrêté à la demande. Les travaux ci-dessous se préparent et se décrivent sans relancer la caméra.

## État actuel

Le modèle est YOLOv8n, via Ultralytics. Les poids `yolov8n.pt` ne sont pas dans Git. La classe demandée est la personne. Le service ne fixe pas de seuil de confiance : toute boîte renvoyée compte. Il n'ignore pas les petites boîtes, ne suit pas la même personne d'une image à l'autre, et ne limite pas l'analyse à une zone de la pièce.

Dès qu'une boîte est présente, l'alerte « Personne détectée devant la caméra » part vers l'API. Un silence de 8 secondes empêche la rafale, puis une nouvelle boîte peut alerter à nouveau, y compris si la personne n'est jamais partie. Il n'y a pas de message de départ.

Le flux annoté est en MJPEG sur le port 8090. Le tableau de bord le demande via le proxy `/video/stream`. L'image affichée suit le rythme de l'analyse : aujourd'hui, chaque image lue est analysée.

YOLOv8n est un poids COCO nano, déjà entraîné sur des photos générales. Il ne connaît pas cette salle. Il suffit quand la personne est proche de la caméra. Un écran ou une affiche qui montre une personne peut encore compter comme une personne.

## Modèles et outils déjà entraînés

Aucun n'est appris sur cette pièce. On les télécharge tels quels. On n'entraîne pas un détecteur maison.

- YOLOv8n, en place. Nano, classe personne. Suffisant de près.
- YOLO11n, puis YOLO26n, si le nano actuel rate encore des gens après les réglages de confiance et de taille de boîte. Ce sont des poids COCO nano, plus récents, toujours légers.
- La taille small d'un de ces détecteurs, seulement si le nano rate des gens loin. Medium et au-dessus sont trop lourds à côté de la pile Docker sur le même laptop.
- ByteTrack, pour suivre une personne déjà détectée et savoir si elle arrive ou si elle part. Ce n'est pas un nouveau détecteur.
- Supervision, pour dessiner une zone utile et ne compter que ce qui s'y trouve. Ce n'est pas un modèle.
- `yolo11n-pose`, seulement si une affiche ou un écran est compté comme une personne. Le poids pose demande un squelette plausible, pas seulement une silhouette.

## Travaux, dans l'ordre

### 1. Confiance et petites boîtes

**Problème.** Toute boîte de la classe personne déclenche l'alerte. Une détection faible, ou une toute petite boîte au fond de l'image, compte autant qu'une personne proche et nette.

**Changement.** Ne garder que les détections dont la confiance est d'environ 0,5. Ignorer les boîtes trop petites pour être une personne dans la zone filmée. L'alerte ne part que si une boîte franchit ces deux filtres.

**Modèle ou outil.** Le même YOLOv8n. Aucun nouvel entraînement. Le seuil et la taille minimale sont des réglages du service.

**Priorité.** Première. Elle réduit les fausses alertes avant d'ajouter un suivi ou un autre poids.

### 2. Alerter à l'arrivée, puis au départ

**Problème.** L'alerte part dès la première boîte, puis se répète après 8 secondes de silence tant qu'une boîte est là. Le départ de la personne ne produit aucun message.

**Changement.** Suivre la personne d'une image à l'autre. Poster une alerte à l'arrivée, puis une alerte au départ. Ne pas répéter l'arrivée tant que le suivi tient. Le silence de 8 secondes ne sert plus de substitut au suivi.

**Modèle ou outil.** ByteTrack, déjà entraîné, branché sur les boîtes de YOLOv8n. Le détecteur reste YOLOv8n.

**Priorité.** Juste après la confiance. Sans boîtes filtrées, le suivi s'accroche aux fausses petites boîtes.

### 3. Résolution

**Problème.** L'image est ramenée à 640×480, et l'inférence tourne à une taille encore plus basse. De près, YOLOv8n suffit. De loin, la personne devient une petite boîte et disparaît, surtout après le filtre du point 1.

**Changement.** Garder YOLOv8n tant que la personne utile est proche. Si des gens loin manquent encore, essayer YOLO11n, puis YOLO26n, toujours en nano COCO. Passer à la taille small seulement si le nano rate ces gens loin. Ne pas passer à medium ni au-dessus : le laptop porte déjà Docker.

**Modèle ou outil.** `yolov8n.pt` aujourd'hui. `yolo11n.pt` et `yolo26n.pt` sont des poids COCO nano déjà entraînés, hors Git comme l'actuel. Aucun ne connaît cette salle. La taille small est le seul cran au-dessus, et seulement en dernier recours.

**Priorité.** Après l'arrivée et le départ. On ne change de poids que si le nano filtré rate un cas réel de personne éloignée.

### 4. Rythme du flux

**Problème.** Chaque image lue est analysée. Sur la caméra du laptop, cela fait plus de calcul que nécessaire, et le flux MJPEG du tableau de bord suit cette cadence.

**Changement.** Analyser 3 à 5 images par seconde. Le flux vers le port 8090 peut rester plus fluide que l'analyse : l'écran montre l'image, le modèle ne traite qu'un extrait régulier. ByteTrack s'appuie sur cet extrait, donc le rythme doit rester stable.

**Modèle ou outil.** Aucun nouveau modèle. C'est un rythme du service, compatible avec YOLOv8n et avec ByteTrack.

**Priorité.** Avec la mise en service du suivi, avant un long essai. Le service reste arrêté tant qu'on ne demande pas explicitement de rouvrir la caméra.

### 5. Zone utile

**Problème.** Tout le cadre compte. Une personne dans un couloir, un reflet, ou un bord de pièce hors du sujet, peut lever l'alerte.

**Changement.** Définir la zone utile de la pièce (l'entrée surveillée, pas tout le cadre). Une boîte ne déclenche l'arrivée que si elle est dans cette zone. Le suivi et le départ utilisent la même zone.

**Modèle ou outil.** Supervision, pour la zone. Le détecteur reste celui retenu aux points précédents.

**Priorité.** Quand la détection et le suivi sont stables. Une zone dessinée trop tôt cache des erreurs de confiance.

### 6. Pose, seulement si un affichage compte comme une personne

**Problème.** La classe personne de COCO reconnaît une silhouette humaine, y compris sur une affiche ou un écran. Si cet objet est dans la zone utile et assez grand, les points 1 à 5 peuvent encore alerter.

**Changement.** N'ajouter la pose que si ce cas se produit vraiment. Exiger un squelette plausible avant de compter une arrivée. Une affiche plate ne doit plus suffire.

**Modèle ou outil.** `yolo11n-pose`, poids COCO déjà entraîné, nano, hors Git. Il ne remplace YOLOv8n que pour ce contrôle. On ne l'active pas par précaution.

**Priorité.** Dernière parmi les changements de détection, et seulement si l'essai le montre.

### 7. Message lisible au tableau de bord

**Problème.** Le texte actuel, « Personne détectée devant la caméra », ne dit pas si la personne arrive ou si elle part. Le tableau de bord affiche le type brut et la source `http`, ce qui ne se lit pas seul.

**Changement.** Deux phrases courtes en français, compréhensibles sans connaître le type technique : une pour l'arrivée, une pour le départ. Elles partent avec l'alerte, pour que la liste du tableau de bord les montre telles quelles. La mise en page de l'écran reste hors de ce fichier ; elle est rappelée dans [plan-ia.md](plan-ia.md).

**Modèle ou outil.** Aucun. Le texte accompagne les événements d'arrivée et de départ du point 2.

**Priorité.** En même temps que le suivi. Un suivi sans phrase claire ne se voit pas à l'écran.

## Rappels de mise en œuvre

Le service vision n'est pas dans Docker. Le relancer ouvre la caméra : ce plan ne le demande pas. Les poids restent hors Git. On ne télécharge pas medium ni un modèle plus lourd. On n'entraîne pas YOLOv8n sur des photos de cette salle dans cette étape : les poids COCO nano, filtrés et suivis, sont le chemin retenu.
