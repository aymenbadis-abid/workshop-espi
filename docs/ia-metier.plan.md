# Plan métier de l'IA — Sentinel-X

Démo de surveillance d'une salle serveurs (Sentinel-X / Excubiae). Quelqu'un devant le tableau de bord doit voir trois choses sans mode d'emploi : la salle chauffe, le gaz bouge, une personne entre ou sort. La carte pose les limites. L'IA constate et nomme. Elle ne dit pas quoi faire : pas de « vous devriez », pas de conseil, pas de chatbot.

## État actuel

L'écran montre quatre courbes (température, humidité, gaz, lumière), l'état du boîtier, une liste d'alertes, la vidéo et les commandes. Un badge « simulé » apparaît sur une courbe quand la dernière mesure le dit. Le mot « réelle » n'est jamais écrit. La liste affiche un code (`anomaly`, `person`, `heat`, `gas`…), la phrase, l'heure, puis un autre code (`ml`, `http`, `mqtt`). On ne sait pas qui a décidé. Les traits 27 °C et 35 °C ne sont pas sur la courbe. Le panneau vidéo pointe toujours vers le flux : caméra arrêtée, l'image est vide et le panneau ne le dit pas. « Temps réel connecté » parle seulement des mesures.

Deux constats d'IA existent déjà.

**Capteurs.** Un modèle de forme, appris uniquement sur le scénario normal du simulateur : pièce fictive vers 24 °C, gaz vers 300, un point toutes les 3 secondes. À chaque mesure, il regarde les 30 dernières températures et les 30 derniers gaz, et répond oui ou non. Un oui devient toujours « Dérive détectée : température et gaz montent ensemble », au plus une fois toutes les 2 minutes. La phrase ne change pas selon la forme. Le silence de ces 2 minutes n'est pas dit. Si le fichier du modèle manque, le score est sauté, les mesures continuent, et l'écran ne le dit pas. Ce modèle ignore si la voie est réelle ou simulée. La salle réelle tourne souvent vers 26–27 °C, et la carte envoie un point toutes les 5 secondes. D'où l'alerte à tort déjà vue vers 26–27 °C : température vraie, gaz fictif.

**Caméra.** Sur le laptop, hors Docker. Le détecteur léger déjà en place ne cherche qu'une personne. Toute boîte compte. L'alerte « Personne détectée devant la caméra » peut revenir après 8 secondes. Le départ n'existe pas. La caméra a été testée, une personne a été vue, puis le service a été arrêté. Rien ici ne demande de le relancer.

**La carte, à part de l'IA.** Chaleur : avertissement dès 27 °C (effacé sous 25 °C), danger dès 35 °C (effacé sous 33 °C). Obscurité stable du boîtier : « Ouverture ou sabotage du boîtier ». Le bouton Fuite de gaz publie « Pic de gaz simulé » : c'est un scénario, pas une mesure. Voyant rouge si chaleur, obscurité ou gaz ; vert sinon. Le buzzer reste coupé.

**Gaz.** Le firmware enregistré (commit 7eda3be) lit le module MQ sur la broche 35. Il chauffe 60 secondes, puis prend cette lecture comme référence. Ensuite il publie le gaz comme réel, et il alerte « Gaz élevé » si l'écart à la référence atteint 400, « Gaz revenu à la normale » s'il redescend sous 250. Pendant la chauffe, le chiffre de gaz reste celui du scénario et porte le badge simulé. Ce firmware n'est pas forcément dans la carte flashée. Tant qu'il ne l'est pas, le gaz à l'écran reste un scénario, et « Gaz élevé » n'arrive pas. Même une fois flashé, l'écran jette la chauffe, le compte du capteur et l'écart : on ne voit qu'un nombre, puis un badge qui disparaît. Le modèle, lui, attend encore un gaz vers 300. Un vrai compte du capteur serait refusé pour de mauvaises raisons. On ne le lui donne pas.

## Étapes

### 1. Faire taire la fausse dérive

**Priorité.** Immédiate. C'est ce qui arrête une alerte fausse sous les yeux du visiteur.

**Problème à l'écran.** Salle calme, température réelle vers 26–27 °C, badge « simulé » sur le gaz : la liste dit quand même que la température et le gaz montent ensemble. Après un flash, la première minute (chauffe) et le saut de chiffre qui suit produiraient la même phrase.

**Ce que l'IA doit faire.** Se taire sur le couple tant que la température et le gaz ne sont pas de même nature, les deux réels ou les deux simulés. Se taire aussi sur un gaz réel tant que le seul modèle disponible est celui du simulateur. Le simulateur, où les deux voies sont fictives et cohérentes, continue d'être jugé avec ce modèle. Fichier absent : pas de score, mesures gardées.

**Résultat.** Quinze minutes de salle calme : aucune « Dérive détectée ». Une ligne dit pourquoi : « Gaz simulé : dérive conjointe inactive », ou « Gaz réel, modèle de salle absent : dérive conjointe inactive ». Les phrases 27 °C, 35 °C et, carte flashée, « Gaz élevé » continuent d'arriver. Le scénario dérive du simulateur finit encore par une alerte.

### 2. Faire lire qui a parlé

**Priorité.** Tout de suite après l'étape 1. Sans ça, une alerte juste reste illisible.

**Problème à l'écran.** La liste mélange des codes. On ne distingue pas la carte, un bouton de scénario, l'IA des capteurs et l'IA de la caméra. Caméra arrêtée, le panneau vidéo est vide. Les courbes ne disent « réelle » que par l'absence de badge. 27 °C et 35 °C ne sont pas dessinés. Après flash, la chauffe du gaz ne se voit pas : le badge « simulé » disparaît et le nombre change d'échelle, ce qui ressemble à une fuite.

**Ce que l'IA doit faire.** Rien de plus. Elle a déjà parlé ou elle s'est tue. L'écran doit montrer ce constat tel quel, à côté de la décision de la carte.

**Résultat.** Une chaleur se lit « Décision de la carte », avec le cas : limite 27 °C, limite 35 °C, ou retour à la normale. Une dérive se lit « Décision de l'IA, capteurs ». Une personne se lit « Décision de l'IA, caméra ». « Pic de gaz simulé » se lit « Scénario ». Chaque courbe dit « réelle » ou « simulée », et une ligne au-dessus résume les quatre. Le panneau vidéo écrit « Caméra arrêtée » quand le flux ne répond pas ; le reste de l'écran continue. Sur la température, deux traits marquent 27 °C et 35 °C comme limites de la carte. Sur le gaz, tant que la chauffe n'est pas finie : « Gaz simulé, capteur en chauffe ». Une fois prêt : « Gaz réel », et l'écart avec la limite de la carte (+400, retour sous +250). Cette vérification se fait sans relancer la caméra. Tant que la carte n'est pas flashée, la ligne de gaz reste « simulé », sans prétendre qu'une chauffe est en cours.

### 3. Que la phrase colle à la courbe

**Priorité.** Dès que l'étape 1 laisse le simulateur parler. La même règle servira le jour où la salle aura son propre couple.

**Problème à l'écran.** Toute alerte de capteurs dit « montent ensemble », même si une seule courbe a bougé, ou si seul le niveau est haut. Deux minutes plus tard, plus rien : on peut croire que la dérive a cessé.

**Ce que l'IA doit faire.** Réserver « montent ensemble » au cas où les deux courbes montent et bougent ensemble. Sinon, nommer la courbe et la forme : niveau, pente ou écart. Les nombres utiles tiennent en une ligne sous la phrase. Tant que le silence de 2 minutes court, cette ligne le dit.

**Résultat.** Une fenêtre où seule la température sort du normal n'affiche pas « montent ensemble ». Une dérive tardive du simulateur, les deux séries en hausse liées, l'affiche. On peut vérifier la phrase sur les courbes. Aucune phrase ne dit quoi faire.

### 4. Apprendre le calme de cette salle

**Priorité.** Après les étapes 1 à 3. Premier constat qui connaît la pièce. Le couple avec le gaz attend l'étape 6.

**Problème à l'écran.** Le seul « normal » connu est une pièce fictive vers 24 °C. Une salle calme vers 26–27 °C n'est pas une dérive, et l'humidité réelle est dessinée sans jamais être commentée. Les traits 27 °C et 35 °C disent un franchissement. Ils ne disent pas qu'une courbe prend une forme inhabituelle en restant sous la limite.

**Ce que l'IA doit faire.** Apprendre 30 à 60 minutes de salle calme, au rythme de la carte (un point toutes les 5 secondes), séparément pour la température et pour l'humidité. Nommer ensuite ce qui a bougé sur une seule courbe. Ne pas parler d'une montée commune. Ne pas toucher à la lumière : l'obscurité du boîtier reste la phrase de la carte. Ne pas apprendre le gaz dans cet enregistrement.

**Résultat.** « Décision de l'IA, capteurs », puis la courbe et la forme. Trente minutes au repos, vers 26–27 °C, ne remplissent pas la liste. Une hausse lente volontaire est nommée. Les phrases 27 °C et 35 °C partent toujours de la carte. Le nom du modèle est en petit sous la phrase, pour qu'on sache lequel a parlé.

### 5. Dire qu'une personne arrive, puis qu'elle part

**Priorité.** Premier changement utile de la caméra. Une photo fixe suffit. La caméra du laptop reste arrêtée tant qu'un essai sur le flux vivant n'est pas demandé.

**Problème à l'écran.** Une boîte faible ou minuscule vaut une personne proche. La même personne peut remplir la liste toutes les 8 secondes. Personne ne dit qu'elle est partie. Tout le cadre compte, y compris un passage hors de l'entrée surveillée.

**Ce que l'IA doit faire.** Ne garder qu'une personne assez nette et assez grande. Suivre la même personne. Une phrase à l'arrivée, une phrase au départ, sans rafale entre les deux. Ne compter l'arrivée que dans la zone utile, l'entrée de la salle. Rester sur le détecteur léger déjà en place. Un fichier un peu plus lourd seulement si une personne loin, utile pour la démo, est encore ratée. Un contrôle de silhouette en plus seulement si une affiche ou un écran est encore compté comme une personne.

**Résultat.** « Décision de l'IA, caméra », puis l'arrivée ou le départ, dans cet ordre. Une personne qui reste ne produit qu'une arrivée. Hors zone, rien. Le panneau « Caméra arrêtée » de l'étape 2 ne change pas.

### 6. Nommer une dérive lente du gaz réel

**Priorité.** Seulement quand la carte flashée a fini sa chauffe et qu'on a 30 à 60 minutes calmes de gaz réel. Jusque-là, la ligne de l'étape 1 tient.

**Problème à l'écran.** « Gaz élevé » est un pic franc par rapport à la référence de la carte, du même genre que 27 °C. Il ne dit pas qu'une hausse lente de la température et du gaz dure depuis deux minutes. « Pic de gaz simulé » est un bouton. Le modèle du simulateur ne connaît pas le compte de ce capteur.

**Ce que l'IA doit faire.** Apprendre le calme du couple sur la salle, au pas de 5 secondes, une fois les deux voies réelles. Nommer la dérive lente avec la phrase de l'étape 3. Laisser le pic franc à la carte, avec une phrase qui ne dit plus « simulé ».

**Résultat.** Salle calme : pas d'alerte de couple. Dérive lente des deux voies : « montent ensemble », au plus une fois toutes les 2 minutes, origine IA capteurs. Pic franc : origine carte, écart et limite visibles grâce à l'étape 2. Le bouton Fuite reste « Scénario » et ne fait pas bouger une courbe réelle.

### 7. Reformuler, seulement si la phrase fixe reste obscure

**Priorité.** Optionnelle. Après que les phrases des étapes précédentes sont à l'écran. On ne l'ajoute pas pour la démo si ces phrases suffisent.

**Problème à l'écran.** Une phrase fixe peut rester sèche (niveau, pente, écart) alors que le fait est déjà calculé.

**Ce que l'IA doit faire.** Un petit modèle déjà entraîné, fichier sur le disque du laptop, sans réseau et sans service à côté. Il reformule en une phrase française un fait déjà calculé. Il ne cherche pas une cause. Il ne propose rien. S'il change un nombre, s'il ajoute un conseil, ou si la phrase est vide, on garde la phrase fixe. On ne l'appelle pas à chaque mesure, seulement au moment d'une alerte dont la phrase fixe ne suffit pas.

**Résultat.** Le visiteur lit la même origine qu'avant, et une phrase qui reprend le fait. Fichier absent : la phrase fixe reste, sans message d'erreur.

## Ce qu'on ne fait pas

- Demander à l'IA une action. Elle constate et nomme. L'admin lit et décide.
- Déplacer 27 °C, 35 °C, leurs retours sous 25 °C et 33 °C, ni la limite de gaz de la carte, dans le modèle.
- Mettre la lumière du boîtier dans un modèle. Le sabotage reste la phrase de la carte.
- Scorer une température réelle avec un gaz simulé, y compris pendant les 60 secondes de chauffe.
- Scorer un gaz réel avec le modèle du simulateur.
- Traiter « Pic de gaz simulé » comme une fuite mesurée, ou le saut de chiffre en fin de chauffe comme une fuite.
- Entraîner un détecteur de personnes sur les photos de cette pièce. Le détecteur léger déjà en place, filtré et suivi, suffit. Pas de gros fichier, pas de carte graphique, pas d'API cloud.
- Changer de famille de modèle tant que le modèle recalée tient le repos de la salle. Si un essai a lieu plus tard, l'écran garde la même origine et une phrase du même genre.
- Appeler un modèle de langue en ligne. Pas de clé, pas de service distant.
- Laisser ce modèle inventer un nombre ou proposer une action.
- Monter une plateforme d'apprentissage, un réentraînement automatique, ou un service d'IA à part.
- Relancer la caméra pour appliquer ce plan.
- Présenter la chauffe ou « Gaz élevé » comme déjà visibles tant que la carte flashée n'est pas celle du dépôt.
