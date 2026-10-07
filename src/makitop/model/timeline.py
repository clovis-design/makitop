"""Montage vidéo non destructif, sur une piste sans chevauchement."""

import math
from dataclasses import dataclass, field, replace
from uuid import uuid4


@dataclass(frozen=True)
class Clip:
    media_id: str
    source_in: float
    source_out: float
    timeline_start: float
    id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self):
        values = (self.source_in, self.source_out, self.timeline_start)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Les positions doivent être finies.")
        if self.source_in < 0 or self.source_out <= self.source_in or self.timeline_start < 0:
            raise ValueError("Portion de vidéo invalide.")

    @property
    def duration(self):
        return self.source_out - self.source_in

    @property
    def end(self):
        return self.timeline_start + self.duration


@dataclass
class Timeline:
    clips: list[Clip] = field(default_factory=list)
    fps: int = 30

    def __post_init__(self):
        if type(self.fps) is not int or not 1 <= self.fps <= 120:
            raise ValueError("Cadence invalide (1 à 120 images/s).")
        ordered = sorted(self.clips, key=lambda clip: clip.timeline_start)
        if len({c.id for c in ordered}) != len(ordered):
            raise ValueError("Identifiants de clips dupliqués.")
        if any(a.end > b.timeline_start + 1e-9
               for a, b in zip(ordered, ordered[1:], strict=False)):
            raise ValueError("Les clips ne peuvent pas se chevaucher sur cette piste.")
        self.clips = ordered

    @property
    def duration(self):
        return max((c.end for c in self.clips), default=0.0)

    def clip_at(self, position):
        return next((c for c in self.clips
                     if c.timeline_start - 1e-9 <= position < c.end - 1e-9), None)

    def append(self, media_id, source_in, source_out):
        clip = Clip(media_id, source_in, source_out, self.duration)
        self.clips.append(clip)
        return clip

    def split(self, position):
        clip = self.clip_at(position)
        if clip is None or position <= clip.timeline_start:
            raise ValueError("Placez le curseur à l'intérieur d'un clip.")
        source_cut = clip.source_in + position - clip.timeline_start
        index = self.clips.index(clip)
        self.clips[index:index + 1] = [
            replace(clip, source_out=source_cut),
            Clip(clip.media_id, source_cut, clip.source_out, position),
        ]

    def remove(self, clip_id):
        """Suppression avec fermeture de l'espace laissé par le clip."""
        clip = next(c for c in self.clips if c.id == clip_id)
        self.clips = [
            replace(c, timeline_start=c.timeline_start - clip.duration)
            if c.timeline_start >= clip.end else c
            for c in self.clips if c.id != clip_id
        ]
