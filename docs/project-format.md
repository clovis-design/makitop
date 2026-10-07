# Format de projet `.makitop`

Un projet est un fichier JSON (UTF-8) portant l'extension `.makitop`, lu et écrit par
`storage/project_file.py`. L'utilisateur l'enregistre où il veut ; chaque projet
contient ses propres médias importés.

```json
{
  "format": "makitop",
  "version": 1,
  "name": "Mon film",
  "media": [
    {"type": "video", "path": "rushs/plage.mp4", "id": "…", "name": "plage",
     "extension": ".mp4", "duration": 12.5, "width": 1920, "height": 1080, "fps": 25.0,
     "video_codec": "h264", "audio_codec": "aac", "sample_rate": 48000, "channels": 2},
    {"type": "image", "path": "D:\\logos\\logo.png", "id": "…", "width": 512, "height": 512}
  ]
}
```

## Décisions

- **Version** : `version` est un entier. Un fichier d'une version plus récente que
  celle connue est refusé avec un message clair. Les migrations s'ajouteront dans
  `storage/migrations.py` quand le format évoluera.
- **Types de médias** : `type` vaut `video`, `audio` ou `image` et correspond aux
  classes `Video`, `Audio` et `Image` de `model/media.py`. Les autres champs sont
  ceux du modèle Pydantic.
- **Identifiants** : chaque média garde son `id` d'un enregistrement à l'autre ; les
  futurs clips s'y référeront.
- **Chemins** : un média situé dans le dossier du projet (ou un sous-dossier) est
  enregistré en chemin relatif, pour qu'on puisse déplacer ou partager le dossier
  entier. Les autres médias gardent leur chemin absolu.
- **Médias introuvables** : à chaque ouverture d'un projet, les médias dont le fichier n'est plus à l'emplacement enregistré sont
  listés dans la fenêtre « Médias introuvables ». Ils restent dans le projet, marqués
  « Introuvable » dans le panneau médias. Relier un média à son nouveau fichier garde
  son `id` et retrouve automatiquement les autres médias manquants du même dossier.
- **Écriture sûre** : l'enregistrement écrit d'abord un fichier `.tmp`, puis le renomme ;
  un plantage pendant l'enregistrement ne corrompt pas le projet existant.

## Hors du fichier de projet

- La liste des projets connus (jusqu'à 100, chacun avec sa date de dernière utilisation)
  est dans `recent.json`, dans le dossier de configuration de l'utilisateur
  (`%APPDATA%\Makitop` sous Windows, `~/Library/Application Support/Makitop` sous macOS,
  `~/.config/Makitop` sous Linux). Un projet y entre quand il est ouvert ou enregistré.
  Elle alimente la page d'accueil, affichée au lancement (projets triés du plus
  récemment utilisé au plus ancien), et le sous-menu « Projets récents » (10 premiers).
- Les décodeurs ouverts, textures Dear PyGui et caches de rendu ne sont jamais
  enregistrés.

## À décider plus tard

- convention de temps commune et paramètres vidéo du projet (résolution, FPS) ;
- pistes, clips, effets et keyframes.
