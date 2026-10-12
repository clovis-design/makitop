"""Projet de montage : ressources importées et timeline non destructive."""

from dataclasses import dataclass, field
from pathlib import Path

from makitop.model.media import Media
from makitop.model.timeline import Timeline


@dataclass
class Project:
    name: str = "Sans titre"
    media: list[Media] = field(default_factory=list)
    timeline: Timeline = field(default_factory=Timeline)

    def find_media(self, path: Path) -> Media | None:
        target = path.resolve()
        return next((m for m in self.media if m.path.resolve() == target), None)

    def add_media(self, media: Media) -> None:
        if self.find_media(media.path) is not None:
            raise ValueError(f"Média déjà importé : {media.path}")
        self.media.append(media)

    def replace_media(self, media: Media) -> None:
        """Remplace le média de même identifiant (par exemple après l'avoir relié)."""
        for index, current in enumerate(self.media):
            if current.id == media.id:
                self.media[index] = media
                return
        raise KeyError(media.id)

    def missing_media(self) -> list[Media]:
        """Médias dont le fichier source n'existe plus à son emplacement."""
        return [m for m in self.media if not m.path.is_file()]
