# Format de projet — conventions à définir

La sauvegarde n'est pas encore implémentée. Ce document réserve les décisions à
formaliser lors de l'ajout de `storage/project_file.py` :

- version explicite du format ;
- identifiants stables pour les médias, pistes, clips, effets et keyframes ;
- convention de temps commune et paramètres vidéo du projet ;
- références aux fichiers sources et politique de résolution des chemins ;
- traitement des médias déplacés ou introuvables ;
- compatibilité et migrations lors des évolutions du format.

Le projet sauvegarde les données et paramètres du montage. Les décodeurs ouverts,
textures Dear PyGui et caches de rendu ne font pas partie du fichier de projet.
