# Makitop

Logiciel de montage vidéo en Python (R5.A.05 / R5.A.06).

## Installation

Prérequis : [uv](https://docs.astral.sh/uv/). uv installe lui-même Python 3.12.

```bash
uv sync
```

## Lancer l'application

```bash
uv run makitop
```

## Tests et qualité

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Organisation du code

```
src/makitop/
├── app.py          point d'entrée (contexte Dear PyGui, viewport, boucle)
├── ui/             interface Dear PyGui
│   ├── main_window.py   fenêtre principale et redimensionnement
│   ├── layout.py        calcul des tailles des zones (testable sans interface)
│   ├── menu_bar.py      barre de menus
│   └── panels/          zones : médias, preview, propriétés, timeline
├── model/          modèles métier (Project, Track, Clip, Effect, Keyframe, Media)
├── engine/         render(t), décodage PyAV, effets OpenCV / Pillow
├── audio/          lecture sounddevice, mixage, effets audio
└── export/         export MoviePy
tests/              tests pytest
```
