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
