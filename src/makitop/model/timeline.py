"""Modèle de timeline : clips positionnés dans le temps."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from makitop.model.media import Media


class BaseClip(ABC):
    """Interface commune à tous les clips de la timeline."""

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
