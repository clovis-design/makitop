# Lecture du montage

## Utilisation

1. Importer puis sélectionner une vidéo : sa prévisualisation source s'affiche.
2. Dans la timeline, régler les points d'entrée/sortie en secondes et cliquer
   **Ajouter la portion**. Elle est ajoutée à la fin du montage.
3. **Voir le montage** bascule de la source vers la timeline. Play/Pause/Stop
   s'appliquent au mode indiqué au-dessus de la preview.
4. Déplacer le curseur puis **Couper au curseur**. La découpe est arrondie à
   l'image du montage la plus proche (30 i/s par défaut).
5. Sélectionner un clip dans la liste et le supprimer pour refermer son espace.
6. Enregistrer le projet : les clips sont conservés dans le format `.makitop` v2.
   Les projets v1 restent lisibles avec une timeline vide.

## Architecture

- `model/timeline.py` : une piste vidéo sans chevauchement, portions sources,
  positions montage, découpe et suppression non destructives.
- `engine/timeline.py` : conversion temps montage → temps source, décodage PyAV,
  respect des timestamps sources (y compris les cadences différentes), adaptation
  à 640×360 avec conservation du rapport d'aspect et noir pour les espaces vides.
- `engine/cache.py` : LRU de 64 Mio pour les images rendues. Clés fondées sur
  l'identité/stat du fichier, le temps source et la résolution. Une modification
  de cut ne réutilise pas l'image d'un ancien temps source. Le cache est volatil.
- `application/timeline_playback.py` : instantané du projet, horloge monotone,
  worker unique propriétaire des décodeurs, anticipation de 8 images, jusqu'à
  3 décodeurs ouverts. Un seek écarte les anciennes requêtes ; aucun worker ne
  met à jour Dear PyGui. En cas de retard, la dernière image prête et due est
  affichée ; le compteur conserve la vitesse du montage. À la fin, la lecture
  s'arrête sur la dernière image. Stop et seek actualisent aussi l'image en pause.
- `ui/panels/timeline/` : commandes et liste des clips, curseur de montage.

La lecture source utilise le même moteur via une timeline temporaire d'un clip.
Le bouton **Play** lit également la première piste audio de la vidéo sur la sortie
audio par défaut. **Pause**, **Stop**, le changement de source et les seeks
interrompent la sortie et invalident les anciens buffers. Une vidéo muette ou un
espace vide dans le montage produit du silence.

- `engine/audio.py` : décodage PyAV séquentiel, rééchantillonnage stéréo à 48 kHz,
  correspondance temps montage / portions sources et silence hors des clips.
- `playback/audio.py` : préchargement borné à environ 0,5 seconde sur un thread
  dédié et sortie `sounddevice` (PortAudio). Le callback ne décode rien et suit
  l'horloge vidéo avec compensation de la latence de sortie. En cas de retard,
  les échantillons manquants sont silencieux plutôt que décalés. Une erreur du
  périphérique est remontée dans l'interface et la vidéo peut continuer.

Les anciens `PlaybackController`/`Player` restent disponibles pour leurs appels
existants mais ne pilotent plus la boucle graphique principale.

## Périmètre et extensions

Cette version est une preview **vidéo avec audio**, sans mixage multipiste, effets ni
export. Le cache d'images sert la relecture et les seeks ; il n'est pas un cache
disque persistant de segments encodés et ne garantit pas le temps réel pour une
source plus lourde que les capacités de décodage de la machine.

Pour ajouter les effets, leur description et leur version devront entrer dans
la clé du cache après composition. Pour un cache de segments lourds, ajouter un
planificateur de rendu, l'invalidation des intervalles dépendants (transitions
comprises), et la lecture des segments produits. Le mixage audio et les réglages
de volume par clip restent des extensions possibles.
