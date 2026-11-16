# Composition et lecture du montage

## Placer plusieurs vidéos et photos dans le cadre

1. Importer les médias. Un clic sur une miniature ouvre sa prévisualisation source.
2. Glisser une miniature dans le cadre, ou utiliser son menu contextuel
   **Ajouter à la composition (nouvelle piste)**. Chaque ajout crée un calque
   sur une nouvelle piste, à la position actuelle du montage (à 0 s depuis le
   mode source). Une photo reçoit initialement une durée de 5 secondes.
3. Choisir **16:9**, **9:16** ou **1:1** au-dessus du cadre.
4. Cliquer sur un calque pour le sélectionner. Le déplacer en faisant glisser
   son intérieur ; tirer les poignées des coins pour le redimensionner en
   conservant ses proportions. On peut ainsi placer plusieurs médias côte à côte.
5. Cocher **Recadrer** et déplacer les poignées au milieu des bords pour rogner
   la source. Le recadrage ne déforme pas l'image et reste réversible : tirer
   les bords vers l'extérieur pour retrouver la partie masquée.
6. **Réinitialiser taille / recadrage** replace le média entier dans le cadre.

Les images transparentes (par exemple un PNG) conservent leur transparence.
Les parties situées hors du cadre sont coupées à l'affichage.

## Pistes, durée et ordre des calques

- Les pistes hautes sont au premier plan ; **Piste 1** est le fond.
- Dans la timeline, déplacer un clip horizontalement change son début ; le
  déplacer verticalement change sa piste. Tirer ses bords ajuste sa durée et,
  pour une vidéo, les points d'entrée/sortie de la source.
- Les propriétés permettent également de régler la piste, le début du clip,
  l'entrée/sortie vidéo ou la durée d'une photo. Valider les champs avec Entrée.
- **Devant / Derrière** échange la piste sélectionnée avec la piste adjacente.
- Cliquer dans la règle ou utiliser le curseur **Position (s)** déplace la lecture.
- Cliquer sur un clip absent à la position courante place la lecture à son début.
- **Supprimer le calque** retire uniquement le clip sélectionné ; les autres
  clips conservent leurs positions temporelles.

## Lecture et son

**Voir le montage** revient à la composition après la prévisualisation d'une
source. **Play / Pause / Stop** contrôlent l'image et le son du mode affiché.
La manipulation à la souris met la lecture en pause pour faciliter l'édition.

Les pistes audio des vidéos actives sont mélangées. Sélectionner chaque vidéo
pour régler son **Volume (%)** entre 0 et 200 %, ou cocher **Muet**. Le mélange
est limité à la plage de sortie audio ; diminuer les volumes si plusieurs sons
forts saturent ensemble. Les photos, vidéos muettes et espaces vides sont silencieux.

Sur Debian/Ubuntu, sounddevice utilise la bibliothèque système PortAudio :

```bash
sudo apt-get install libportaudio2
```

## Sauvegarde et architecture

Le format `.makitop` v3 conserve le format du cadre, la cadence, les pistes,
positions, tailles, recadrages, volumes et états muets. Les projets v1 et les
deux variantes historiques du format v2 restent lisibles.

- `model/composition.py` : géométrie normalisée, ajustement sans déformation,
  déplacement, redimensionnement et recadrage.
- `application/composition.py` : édition du projet, sélection, bascule
  source/montage et actualisation des instantanés du lecteur.
- `engine/timeline.py` : composition des vidéos et images actives du fond vers
  le premier plan, transparence, découpe au cadre et cache mémoire borné.
- `engine/audio.py` : décodage PyAV, stéréo à 48 kHz, un décodeur par occurrence
  audio active, volume par clip et sommation des pistes.
- `application/timeline_playback.py` : horloge monotone, instantané du projet,
  décodage vidéo hors UI et anticipation des images. Un seek invalide les requêtes
  obsolètes ; la fin du montage conserve la dernière image.
- `playback/audio.py` : préchargement borné à environ 0,5 seconde sur un thread
  dédié, sortie sounddevice avec compensation de latence. Le callback audio ne
  décode rien ; un retard de décodage produit du silence plutôt qu'un décalage.
- `ui/panels/preview.py`, `properties.py` et `timeline/` : interactions souris,
  réglages et pistes. Les workers ne modifient pas l'interface.

Le cache reste en mémoire et ne garantit pas le temps réel pour des sources ou
un nombre de calques dépassant les capacités de décodage de la machine.
