# Architecture de Makitop

## État actuel

L'application Dear PyGui importe les médias, enregistre les projets et lit une
timeline vidéo non destructive. La timeline permet l'ajout de portions, la découpe
et la suppression avec fermeture de l'espace. Le décodage est exécuté dans un
worker, avec préchargement et cache mémoire borné. Voir
[Lecture du montage](timeline-playback.md) pour l'utilisation, les composants
implémentés et les limites actuelles (notamment l'absence de sortie audio).
`app.py` assemble les composants et gère la boucle graphique. Les modules listés
ci-dessous décrivent aussi des extensions futures, pas toutes implémentées.

## Responsabilités et dépendances

- `app.py` assemble les composants et démarre l'interface.
- `ui/` affiche les données et transmet les interactions à `application/`.
- `application/` coordonne les actions, le modèle et les composants techniques.
- `model/` décrit le montage sans dépendre de Dear PyGui ou des bibliothèques multimédias.
- `media/` inspecte les fichiers et produit les miniatures et formes d'onde.
- `engine/` calcule les images et les blocs audio du montage.
- `playback/` restitue ces résultats en temps réel et synchronise l'audio et la vidéo.
- `export/` encode les résultats du moteur dans un fichier.
- `storage/` lit et écrit les projets.

Les composants techniques peuvent utiliser le modèle mais n'importent pas l'interface.
La prévisualisation et l'export doivent partager les règles de rendu du moteur.
L'ancien emplacement `audio/`, qui ne contenait aucune implémentation, est réparti
entre `playback/` (sortie), `engine/` (mixage) et `engine/effects/` (effets).

## Modules à ajouter avec les fonctionnalités

| Package | Modules prévus |
| --- | --- |
| `model/` | `project.py`, `media.py`, `timeline.py`, `track.py`, `clip.py`, `effect.py`, `keyframe.py`, `time.py` |
| `application/` | `state.py`, `projects.py`, `media.py`, `editor.py`, `playback.py`, `export.py`, `jobs.py`, `history.py` |
| `application/commands/` | `base.py`, `clips.py`, `tracks.py`, `effects.py` |
| `media/` | `probe.py`, `thumbnails.py`, `waveforms.py` |
| `engine/` | `renderer.py`, `decoder.py`, `compositor.py`, `audio_mixer.py`, `cache.py` |
| `engine/effects/` | `registry.py`, `video.py`, `audio.py` |
| `playback/` | `player.py`, `clock.py`, `audio_output.py` |
| `export/` | `encoder.py`, `settings.py` |
| `storage/` | `project_file.py`, `serialization.py`, puis `migrations.py` |
| `ui/` | `shortcuts.py`, `theme.py` |
| `ui/dialogs/` | `import_media.py`, `export.py`, `project_settings.py` |

Les fichiers sont créés lorsqu'ils ont une responsabilité concrète à implémenter.
Un média représente une ressource ; un clip représente son utilisation dans la timeline.
L'état de sélection et de navigation appartient à l'éditeur, pas aux clips.
La description d'un effet appartient au modèle, son traitement au moteur.

## Timeline et compatibilité

Le panneau existant est déplacé dans `ui/panels/timeline/panel.py` sans changer
son contenu. Le package `timeline` réexporte `TAG` et `create` pour préserver les
imports de la fenêtre principale. Les futurs modules `drawing.py`,
`interactions.py` et `coordinates.py` accueilleront les responsabilités distinctes.

## Tests

- `tests/unit/ui/test_layout.py` vérifie le calcul pur des dimensions.
- `tests/integration/test_main_window.py` vérifie les widgets dans un contexte Dear PyGui.
- Les autres répertoires de tests accueilleront les tests des futures fonctionnalités.
- `tests/fixtures/` est réservé aux petits médias et projets de test.

Les commandes restent `uv run makitop`, `uv run pytest` et `uv run ruff check .`.
