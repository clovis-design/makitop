# Makitop

Logiciel de montage vidéo en Python (R5.A.05 / R5.A.06).

## Installation

Prérequis : [uv](https://docs.astral.sh/uv/). uv installe lui-même Python 3.12.

```bash
uv sync
```

La sortie audio utilise **sounddevice**, qui s'appuie sur **PortAudio**. Sur
Debian/Ubuntu, installer également la bibliothèque système :

```bash
sudo apt-get install libportaudio2
```

## Lancer l'application

```bash
uv run makitop
```

## Composer plusieurs médias

Glisser une vidéo ou une photo depuis les médias vers le cadre de prévisualisation.
Chaque ajout crée une nouvelle piste. Dans le lecteur, les poignées gauche et
droite règlent la largeur ; celles du haut et du bas règlent la hauteur.
Les coins conservent les proportions. Activez **Recadrer** pour rogner les
bords au lieu de redimensionner.

Sous Linux, le curseur natif change au survol et pendant le glissement sur le
cadre, ses bords et ses poignées, ainsi que sur la barre de lecture. Si le
backend GLFW ne permet pas ce changement, le curseur standard reste affiché.
Le format du cadre (16:9, 9:16, 1:1) se choisit au-dessus de la composition.

Dans **Propriétés → Vidéo → Transformation**, **Rotation** fait pivoter le
calque, **Miroir horizontal** inverse la gauche et la droite, et **Miroir vertical**
inverse le haut et le bas. Hors mode
**Recadrer**, la poignée ronde du lecteur permet aussi de faire pivoter
le calque sélectionné avec la souris.

La timeline règle la position et la durée des clips ; le panneau **Propriétés**
permet de changer leur ordre, leur volume ou de les rendre muets.
Voir le [guide de composition et de lecture](docs/timeline-playback.md).

Dans **Propriétés → Vidéo → Temps**, le curseur **Vitesse** propose des valeurs
prédéfinies de **0,25× à 8×** et s'applique au clip
sélectionné : à **2×**, un clip de deux minutes n'occupe plus qu'une minute.
Le début du clip et sa coupe source sont conservés ; ses images clés suivent
le changement de vitesse. L'image et le son sont accélérés ou ralentis
ensemble, sans correction de la hauteur du son.

### Ajouter du texte

Placer la tête de lecture, ouvrir **Texte** dans la barre latérale et cliquer sur
une vignette : **Titre**, **Intertitre**, **Sous-titre**, **Paragraphe**,
**Citation**, **Légende**, **Cartouche**, **Chapitre** ou **Générique**. Le clip
apparaît devant par défaut. L’ordre est commun aux textes, images et vidéos :
les pistes plus hautes passent devant. Utiliser **Devant** ou **Derrière** dans
les propriétés, les flèches des pistes, ou déplacer le clip dans la timeline.
Sa zone peut aussi être déplacée directement dans le lecteur.

La catégorie **Styles typographiques** propose aussi **Éditorial**, **Élégant**
et **Terminal**, avec des polices intégrées qui ne dépendent pas de la machine.

Sélectionner le clip pour ouvrir l'onglet **Texte** des propriétés : modifier le
contenu, la police, la taille, la couleur, l'alignement, la zone et la durée. Le texte est
enregistré dans le projet et apparaît aussi dans le MP4 exporté. L’onglet
**Images clés** permet d’animer la position, les dimensions, le zoom et
l’opacité du texte (par exemple pour un fondu).

Un réglage animé est grisé dans les autres onglets : cliquer sur **◆ Animé**
ouvre sa clé la plus proche dans **Images clés**. Retirer sa dernière clé
réactive le réglage.

### Qualité et fluidité du lecteur

Au-dessus du cadre, choisir la cadence du montage : **24, 25, 30, 48, 50, 60,
90 ou 120 fps**. Les nouveaux projets démarrent à **60 fps** ; les projets existants
conservent leur cadence enregistrée. Modifier la cadence ne déplace pas les clips
et ne change pas leur durée. La lecture d'un média source utilise sa propre cadence
(arrondie à l'entier supérieur, jusqu'à 120 fps).

La qualité de prévisualisation est indépendante de l'export :
- **HD (720p)** par défaut : compromis entre netteté et fluidité ;
- **Full HD (1080p)** : plus de détails, davantage de calcul et de mémoire ;
- **Fluide (360p)** : pour les montages lourds ou les machines moins puissantes.

Le lecteur conserve la résolution choisie jusqu'à la texture d'affichage, avec
préchargement des images en arrière-plan. La cadence effectivement visible dépend
du décodage, du nombre de calques, du GPU et du taux de rafraîchissement de l'écran.
Une source à 30 fps reste à 30 images de mouvement différentes par seconde, même
dans un montage à 120 fps : aucune interpolation artificielle n'est appliquée.

## Animer avec des images clés

Les propriétés **Position X, Position Y, Largeur, Hauteur et Volume** peuvent évoluer
dans le temps, sur les vidéos comme sur les images fixes (volume pour les médias sonores).

1. Sélectionner un clip et placer la tête de lecture au début de l'animation.
2. Dans **Propriétés**, régler la valeur puis cliquer sur **+ clé** à côté du réglage.
3. Avancer la tête de lecture et modifier cette propriété : une nouvelle image clé
   est créée automatiquement dès que la propriété possède déjà une animation.
   Le déplacement/redimensionnement à la souris suit la même règle.
4. Lancer la lecture : les valeurs intermédiaires sont calculées automatiquement.

Cocher **Images clés** dans la timeline pour déplier les cinq lignes sous la piste
du clip sélectionné. Les clés sont des **losanges bleus**, et la clé sélectionnée
est **jaune**. Cliquer sur un losange place la lecture à cet instant ; le glisser
horizontalement déplace la clé, avec alignement sur la cadence du projet au relâchement.
Le déplacement sur une clé existante de la même propriété est refusé.

Dans les propriétés, **Précédente / Suivante** permettent de naviguer entre les clés.
Le temps de la clé sélectionnée est aussi modifiable numériquement. Son interpolation
vers la clé suivante se règle sur **Linéaire**, **Douce** (départ/arrivée progressifs)
ou **Constante** (changement instantané à la clé suivante).
Utiliser **Supprimer cette clé**, le bouton de la timeline ou **- clé** à l'instant
concerné pour la supprimer.

Les temps sont relatifs au début du clip : déplacer le clip déplace toute son animation.
Les valeurs avant la première clé et après la dernière sont maintenues. Raccourcir
un clip conserve ses clés hors durée pour pouvoir le rallonger ensuite.
**Réinitialiser taille / recadrage** efface aussi l'animation de position et de taille,
en conservant celle du volume. L'animation est enregistrée dans le projet et appliquée
à l'identique par les moteurs du lecteur et de l'export ; le volume est interpolé
échantillon par échantillon.

## Ajouter une transition

Dans la timeline, placez deux vidéos ou images à la suite ou faites-les se
chevaucher. Sélectionnez le **clip d’arrivée**, puis cliquez sur une vignette
dans **Transitions**. Le catalogue couvre les préréglages vidéo de
[FFmpeg `xfade`](https://ffmpeg.org/ffmpeg-filters.html#xfade) : fondus,
balayages, glissements, iris, diagonales, bandes, zoom et autres effets.
Les préréglages disponibles dépendent de la version de FFmpeg fournie par PyAV.

Le repère **T** indique la zone dans la timeline. Dans **Propriétés →
Transition**, modifiez sa durée ou retirez-la. Les clips ne sont pas déplacés :
sur une coupe, la transition est centrée sur la jonction ; quand les clips se
chevauchent, elle démarre au début du chevauchement. Sa durée est limitée par
la place disponible. Le lecteur et l’export utilisent le même rendu, y compris
le fondu audio lorsque les sources ont du son.

## Exporter en MP4

Dans l'éditeur, choisir **Fichier → Exporter...**, régler la qualité, puis choisir
le fichier de destination :
- **Résolution** : HD, Full HD ou 4K, en conservant le format paysage/portrait/carré
  du projet (par exemple 3840×2160 en 4K paysage).
- **Cadence** : celle du projet par défaut, ou une cadence spécifique jusqu'à
  **120 fps**, sans modifier la timeline.
- **Qualité** : haute qualité (H.264 CRF 18, medium), maximale (CRF 16, slow),
  ou rapide (CRF 20, fast). Un CRF plus faible privilégie les détails et produit
  généralement un fichier plus volumineux.

Le son est encodé en AAC stéréo à 48 kHz, 256 kbit/s, avec les coupes, calques,
recadrages et volumes du montage. Les espaces entre les clips restent noirs et
silencieux. L'export travaille à la résolution demandée, indépendamment de la
qualité du lecteur ; augmenter la résolution ne recrée pas les détails absents
du média source.

Une fenêtre affiche la progression et permet d'annuler. L'interface reste disponible ;
l'export conserve le montage tel qu'il était au lancement. Un fichier de destination
existant est remplacé uniquement si l'export réussit.

## Tests et qualité

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Organisation du code

```
src/makitop/
├── app.py          assemblage et cycle de vie de l'application
├── model/          données et règles du montage
├── application/    actions utilisateur et coordination
│   └── commands/   modifications annulables du montage
├── ui/             interface Dear PyGui
│   ├── main_window.py   fenêtre principale et redimensionnement
│   ├── layout.py        calcul des tailles, indépendant de Dear PyGui
│   ├── menu_bar.py      barre de menus
│   ├── panels/          médias, preview, propriétés et package timeline/
│   ├── dialogs/         boîtes de dialogue
│   └── assets/          icônes et polices
├── media/          inspection des fichiers, miniatures et formes d'onde
├── engine/         décodage, composition vidéo et mixage audio
│   └── effects/    traitements vidéo et audio
├── playback/       lecture temps réel et synchronisation audio/vidéo
├── export/         encodage du résultat final
└── storage/        sauvegarde et chargement des projets
tests/
├── unit/           logique testable isolément
├── integration/    assemblage de l'interface et des composants
└── fixtures/       futurs petits médias et projets de test
```

L'interface constitue pour l'instant un squelette fonctionnel. Les nouveaux packages
préparent les fonctionnalités à venir ; leurs modules seront ajoutés progressivement.
Voir [l'architecture détaillée](docs/architecture.md) et les
[conventions du futur format de projet](docs/project-format.md).
