"""Média importé : une ressource (fichier source) et ses caractéristiques techniques.

Un média n'est pas un clip : le clip représente l'utilisation d'un média dans la timeline.
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class MediaKind(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"


@dataclass(frozen=True)
class Media:
    path: Path
    kind: MediaKind
    # Durée en secondes ; None pour une image fixe.
    duration: float | None = None
    # Vidéo et image.
    width: int | None = None
    height: int | None = None
    # Vidéo.
    fps: float | None = None
    video_codec: str | None = None
    # Vidéo avec son, ou audio seul.
    audio_codec: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def has_audio(self) -> bool:
        return self.audio_codec is not None
