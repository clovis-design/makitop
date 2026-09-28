"""Projet de montage. Pour l'instant, il ne contient que les médias importés."""

from dataclasses import dataclass, field
from pathlib import Path

from makitop.model.media import Media


@dataclass
class Project:
    name: str = "Sans titre"
    media: list[Media] = field(default_factory=list)

    def find_media(self, path: Path) -> Media | None:
        target = path.resolve()
        return next((m for m in self.media if m.path.resolve() == target), None)

    def add_media(self, media: Media) -> None:
        if self.find_media(media.path) is not None:
            raise ValueError(f"Média déjà importé : {media.path}")
        self.media.append(media)
