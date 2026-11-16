"""Projet de montage : médias importés et timeline."""

from dataclasses import dataclass, field
from pathlib import Path

from makitop.model.composition import FORMATS
from makitop.model.media import Media
from makitop.model.timeline import Timeline


@dataclass
class Project:
    name: str = "Sans titre"
    media: list[Media] = field(default_factory=list)
    timeline: Timeline = field(default_factory=Timeline)
    canvas_format: str = "16:9"

    def __post_init__(self):
        if self.canvas_format not in FORMATS:
            raise ValueError("Format de composition inconnu.")

    @property
    def canvas_ratio(self):
        width, height = FORMATS[self.canvas_format]
        return width / height

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
                for clip in self.timeline.clips:
                    if clip.media.id == media.id:
                        clip.media = media
                return
        raise KeyError(media.id)

    def missing_media(self) -> list[Media]:
        """Médias dont le fichier source n'existe plus à son emplacement."""
        return [m for m in self.media if not m.path.is_file()]
