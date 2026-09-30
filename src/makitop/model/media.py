"""Média importé : une ressource (fichier source) et ses caractéristiques techniques.

Un média n'est pas un clip : le clip représente l'utilisation d'un média dans la timeline.
"""

import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Media(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path
    name: str = ""
    extension: str = ""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)

    @model_validator(mode="after")
    def _defaults(self) -> "Media":
        if not self.name:
            object.__setattr__(self, "name", self.path.stem)
        if not self.extension:
            object.__setattr__(self, "extension", self.path.suffix.lower())
        return self

    @property
    def has_audio(self) -> bool:
        return isinstance(self, (Video, Audio)) and getattr(self, "audio_codec", None) is not None


class Video(Media):
    duration: float | None = None
    width: int
    height: int
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    sample_rate: int | None = None
    channels: int | None = None


class Audio(Media):
    duration: float | None = None
    audio_codec: str
    sample_rate: int | None = None
    channels: int | None = None


class Image(Media):
    width: int
    height: int
