# Format des projets `.makitop`

Un projet est un document JSON UTF-8. La version actuelle est **5**.

```json
{
  "format": "makitop",
  "version": 5,
  "name": "Mon montage",
  "canvas_format": "16:9",
  "fps": 30,
  "media": [
    {"id": "video-1", "type": "video", "path": "rushs/plan.mp4",
     "duration": 12.5, "width": 1920, "height": 1080, "fps": 25,
     "video_codec": "h264", "audio_codec": "aac", "sample_rate": 48000, "channels": 2}
  ],
  "timeline": [
    {
      "clip_type": "media",
      "id": "clip-1",
      "media_id": "video-1",
      "timeline_start": 0.0,
      "source_start": 1.0,
      "source_end": 8.0,
      "track": 0,
      "transform": {
        "x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0,
        "crop_left": 0.0, "crop_top": 0.0, "crop_right": 0.0, "crop_bottom": 0.0
      },
      "volume": 0.8,
      "muted": false,
      "effects": [],
      "keyframes": [
        {"property": "x", "time": 0.0, "value": 0.0, "interpolation": "smooth"},
        {"property": "x", "time": 3.0, "value": 0.5, "interpolation": "linear"}
      ]
    }
  ],
  "view": {"playhead": 2.3, "timeline_zoom": 100}
}
```

## Règles

- **Cadre** : `canvas_format` vaut `16:9`, `9:16` ou `1:1`. `fps` est une cadence
  entière entre 1 et 120 images/s. Nouveaux projets : 16:9 et 60 images/s.
  Un ancien fichier sans cadence est interprété à 30 images/s.
- **Médias** : ressources importées de type `video`, `audio` ou `image`.
  Les chemins situés dans le dossier du projet sont relatifs ; les autres sont
  absolus. Les identifiants sont stables entre deux sauvegardes.
- **Clips** : occurrences des ressources dans le montage. `clip_type: media`
  possède `source_start` et `source_end` ; `clip_type: image` possède à leur place
  `display_duration`. La durée d'une portion vidéo est `source_end - source_start`.
  Les temps sont exprimés en secondes et les intervalles excluent leur fin.
- **Pistes** : indices de 0 à 99. La piste 0 est le fond ; une piste supérieure
  se dessine par-dessus. Sur la même piste, les occurrences simultanées suivent
  l'ordre de la liste (la dernière se dessine devant). Leurs sons sont additionnés.
- **Géométrie** : `x`, `y`, `width` et `height` sont relatifs au cadre (0 à 1 pour
  ses dimensions nominales). La source recadrée est ajustée dans ce rectangle en
  conservant ses proportions. Une position peut déborder ; l'image est coupée au
  cadre. Les quatre marges `crop_*` sont des fractions des dimensions sources.
- **Audio** : gain linéaire `volume` entre 0 et 2 ; `muted` coupe l'occurrence.
  Les transformations visuelles ne modifient pas l'audio.
- **Images clés** : liste `keyframes`, vide par défaut. Chaque clé contient une
  `property` parmi `x`, `y`, `width`, `height`, `volume`, un `time` fini positif ou nul
  relatif au début du clip, une `value` dans les mêmes unités et limites que la
  propriété constante, et une `interpolation` (`linear`, `smooth`, `constant`).
  Cette interpolation décrit le segment vers la clé suivante de la même propriété.
  Deux clés ne peuvent pas partager la même propriété et le même instant.
  Les valeurs extrêmes sont maintenues hors des clés. Les temps ne changent pas
  quand le clip est déplacé ou quand la cadence est modifiée. Les clés après une
  nouvelle fin de clip sont conservées lors d'un raccourcissement.
- **État d'affichage** : `view.playhead` est la position de lecture en secondes
  (timeline et preview), `view.timeline_zoom` le zoom de la timeline en pixels par
  seconde. Ils sont restaurés à l'ouverture ; les modifier marque le projet comme
  modifié. Réordonner les lignes de la timeline renumérote les pistes 0, 1, 2…
  (la ligne du bas passe devant).
- **Sauvegarde atomique** : écriture dans un fichier temporaire puis remplacement
  du projet. Les fichiers sources restent inchangés.

## Compatibilité

- Les projets v1 sans timeline s'ouvrent avec un montage vide.
- La variante v2 avec une liste de `MediaClip` / `ImageClip` reste lisible.
- La variante v2 avec `timeline: {fps, clips}` et des bornes `source_in` /
  `source_out` est convertie à la lecture.
- Les anciens clips reçoivent par défaut la piste 0, une géométrie plein cadre
  avec conservation des proportions, le volume 1 et `muted: false`.
- Un projet sans `view` s'ouvre avec la lecture à 0 et un zoom de 100 px/s.
- Les projets v4 (effets) restent lisibles ; les clips sans `keyframes` restent constants.
- Une version plus récente que celle comprise par l'application est refusée.
  L'enregistrement d'un ancien projet produit le format v5.

## Ressources externes

Les médias manquants peuvent être reliés à leurs nouveaux chemins. La mise à jour
conserve leur identifiant et actualise les occurrences dans la timeline.
La liste des projets récents appartient au fichier de configuration `recent.json`.
Les décodeurs, textures et caches de rendu ne sont jamais sérialisés.
