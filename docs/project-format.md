# Format des projets `.makitop`

Un projet est un document JSON UTF-8. La version actuelle est **3**.

```json
{
  "format": "makitop",
  "version": 3,
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
      "muted": false
    }
  ]
}
```

## Règles

- **Cadre** : `canvas_format` vaut `16:9`, `9:16` ou `1:1`. `fps` est une cadence
  entière entre 1 et 120 images/s. Par défaut : 16:9 et 30 images/s.
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
- **Sauvegarde atomique** : écriture dans un fichier temporaire puis remplacement
  du projet. Les fichiers sources restent inchangés.

## Compatibilité

- Les projets v1 sans timeline s'ouvrent avec un montage vide.
- La variante v2 avec une liste de `MediaClip` / `ImageClip` reste lisible.
- La variante v2 avec `timeline: {fps, clips}` et des bornes `source_in` /
  `source_out` est convertie à la lecture.
- Les anciens clips reçoivent par défaut la piste 0, une géométrie plein cadre
  avec conservation des proportions, le volume 1 et `muted: false`.
- Une version plus récente que celle comprise par l'application est refusée.
  L'enregistrement d'un ancien projet produit le format v3.

## Ressources externes

Les médias manquants peuvent être reliés à leurs nouveaux chemins. La mise à jour
conserve leur identifiant et actualise les occurrences dans la timeline.
La liste des projets récents appartient au fichier de configuration `recent.json`.
Les décodeurs, textures et caches de rendu ne sont jamais sérialisés.
