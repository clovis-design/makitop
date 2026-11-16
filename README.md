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
Chaque ajout crée une nouvelle piste. Déplacer le calque à la souris, tirer ses
coins pour le redimensionner, ou activer **Recadrer** pour rogner ses bords.
Le format du cadre (16:9, 9:16, 1:1) se choisit au-dessus de la composition.

La timeline règle la position et la durée des clips ; le panneau **Propriétés**
permet de changer leur ordre, leur volume ou de les rendre muets.
Voir le [guide de composition et de lecture](docs/timeline-playback.md).

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
