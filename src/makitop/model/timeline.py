"""Modèle de timeline : clips positionnés dans le temps."""

from __future__ import annotations

import math
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from makitop.model.composition import Transform
from makitop.model.media import Media


@dataclass(kw_only=True)
class BaseClip(ABC):
    """Interface commune à tous les clips de la timeline."""

    track: int = 0
    transform: Transform = field(default_factory=Transform)
    volume: float = 1.0
    muted: bool = False

    def __post_init__(self):
        if type(self.track) is not int or not 0 <= self.track <= 99:
            raise ValueError("La piste doit être comprise entre 0 et 99.")
        if not math.isfinite(self.volume) or not 0 <= self.volume <= 2:
            raise ValueError("Le volume doit être compris entre 0 et 200 %.")
        if not math.isfinite(self.timeline_start) or self.timeline_start < 0:
            raise ValueError("Position de clip invalide.")
        if not math.isfinite(self.duration) or self.duration <= 0:
            raise ValueError("La durée du clip doit être positive.")
        if isinstance(self, MediaClip):
            if not math.isfinite(self.source_start) or self.source_start < 0:
                raise ValueError("Point d'entrée invalide.")
            if self.media.duration is not None and self.source_end > self.media.duration + 1e-6:
                raise ValueError("Le point de sortie dépasse la durée du média.")

    @property
    @abstractmethod
    def timeline_end(self) -> float: ...

    @property
    def duration(self) -> float:
        return self.timeline_end - self.timeline_start  # type: ignore[attr-defined]


@dataclass
class MediaClip(BaseClip):
    """Portion d'un fichier vidéo ou audio, positionnée sur la timeline."""

    timeline_start: float
    media: Media
    source_start: float
    source_end: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def timeline_end(self) -> float:
        return self.timeline_start + (self.source_end - self.source_start)


@dataclass
class ImageClip(BaseClip):
    """Image statique dont la durée d'affichage est définie manuellement."""

    timeline_start: float
    media: Media
    display_duration: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def timeline_end(self) -> float:
        return self.timeline_start + self.display_duration


@dataclass
class Timeline:
    clips: list[BaseClip] = field(default_factory=list)
    fps: int = 30

    def __post_init__(self):
        if type(self.fps) is not int or not 1 <= self.fps <= 120:
            raise ValueError("Cadence invalide.")
        if len({c.id for c in self.clips}) != len(self.clips):
            raise ValueError("Identifiants de clips dupliqués.")

    def clips_at(self, position):
        """Calques actifs du fond vers le premier plan (piste supérieure)."""
        return sorted((c for c in self.clips
                       if c.timeline_start - 1e-9 <= position < c.timeline_end - 1e-9),
                      key=lambda c: c.track)

    @property
    def duration(self) -> float:
        if not self.clips:
            return 0.0
        return max(c.timeline_end for c in self.clips)

    def clip_at(self, position: float) -> BaseClip | None:
        return next(
            (c for c in self.clips
             if c.timeline_start - 1e-9 <= position < c.timeline_end - 1e-9),
            None,
        )

    def add_clip(self, clip: BaseClip) -> None:
        self.clips.append(clip)

    def remove_clip(self, clip_id: str) -> None:
        self.clips = [c for c in self.clips if c.id != clip_id]
