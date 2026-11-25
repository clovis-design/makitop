"""Modèle de timeline : clips positionnés dans le temps."""

from __future__ import annotations

import math
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace

from makitop.model.composition import Transform, with_zoom
from makitop.model.effects import Effect
from makitop.model.keyframes import GEOMETRY_PROPERTIES, Keyframe, curve, value_at
from makitop.model.media import Media, MediaKind
from makitop.model.text import MAX_TEXT_LENGTH, TextStyle
from makitop.model.transitions import Transition, span_for

MIN_CLIP_SPEED, MAX_CLIP_SPEED = 0.25, 8.0


@dataclass(kw_only=True)
class BaseClip(ABC):
    """Interface commune à tous les clips de la timeline."""

    track: int = 0
    transform: Transform = field(default_factory=Transform)
    volume: float = 1.0
    muted: bool = False
    effects: tuple[Effect, ...] = ()
    keyframes: tuple[Keyframe, ...] = ()

    def __post_init__(self):
        if not isinstance(self.keyframes, tuple) or not all(
            isinstance(k, Keyframe) for k in self.keyframes
        ):
            raise ValueError("Liste d'images clés invalide.")
        if len({(k.property, k.time) for k in self.keyframes}) != len(self.keyframes):
            raise ValueError("Images clés dupliquées.")
        if not isinstance(self.effects, tuple) or not all(
            isinstance(e, Effect) for e in self.effects
        ):
            raise ValueError("Liste d'effets invalide.")
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

    @property
    @abstractmethod
    def label(self) -> str: ...

    @property
    def keyframe_properties(self):
        return (*GEOMETRY_PROPERTIES, "volume")

    def unzoomed_transform_at(self, local_time):
        if not self.keyframes:
            return self.transform
        return replace(self.transform, **{
            name: value_at(self.keyframes, name, local_time, getattr(self.transform, name))
            for name in ("x", "y", "width", "height")
        })

    def transform_at(self, local_time):
        transform = self.unzoomed_transform_at(local_time)
        if curve(self.keyframes, "zoom"):
            # Le zoom conserve les proportions et le centre, après les autres animations.
            transform = with_zoom(transform, value_at(
                self.keyframes, "zoom", local_time, self.transform.width,
            ))
        return transform

    def volume_at(self, local_time):
        return value_at(self.keyframes, "volume", local_time, self.volume)


@dataclass
class MediaClip(BaseClip):
    """Portion d'un fichier vidéo ou audio, positionnée sur la timeline."""

    timeline_start: float
    media: Media
    source_start: float
    source_end: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    speed: float = field(default=1.0, kw_only=True)

    def __post_init__(self):
        if (type(self.speed) not in (int, float)
                or not MIN_CLIP_SPEED <= self.speed <= MAX_CLIP_SPEED):
            raise ValueError("La vitesse doit être comprise entre 0,25× et 8×.")
        super().__post_init__()

    @property
    def timeline_end(self) -> float:
        return self.timeline_start + self.duration

    @property
    def duration(self) -> float:
        return (self.source_end - self.source_start) / self.speed

    def source_time_at(self, position: float) -> float:
        """Instant du média correspondant à une position dans le montage."""
        return self.source_start + max(0.0, position - self.timeline_start) * self.speed

    @property
    def label(self) -> str:
        return self.media.name


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

    @property
    def label(self) -> str:
        return self.media.name


@dataclass
class TextClip(BaseClip):
    """Zone de texte intégrée au projet, sans média associé."""

    timeline_start: float
    display_duration: float
    content: str
    style: TextStyle = field(default_factory=TextStyle)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.content, str) or len(self.content) > MAX_TEXT_LENGTH:
            raise ValueError(f"Le texte ne doit pas dépasser {MAX_TEXT_LENGTH} caractères.")
        if not isinstance(self.style, TextStyle):
            raise ValueError("Style de texte invalide.")

    @property
    def timeline_end(self) -> float:
        return self.timeline_start + self.display_duration

    @property
    def label(self) -> str:
        return next((line.strip() for line in self.content.splitlines() if line.strip()), "Texte")

    @property
    def keyframe_properties(self):
        return (*GEOMETRY_PROPERTIES, "opacity")

    def opacity_at(self, local_time):
        return value_at(self.keyframes, "opacity", local_time, 1.0)

    def font_scale_at(self, local_time, transform):
        if not any(key.property == "zoom" for key in self.keyframes):
            return 1.0
        width = value_at(self.keyframes, "width", local_time, self.transform.width)
        return transform.width / width


@dataclass
class Timeline:
    clips: list[BaseClip] = field(default_factory=list)
    fps: int = 30
    transitions: tuple[Transition, ...] = ()

    def __post_init__(self):
        if type(self.fps) is not int or not 1 <= self.fps <= 120:
            raise ValueError("Cadence invalide.")
        if len({c.id for c in self.clips}) != len(self.clips):
            raise ValueError("Identifiants de clips dupliqués.")
        clips = {c.id for c in self.clips
                 if isinstance(c, (ImageClip, MediaClip)) and c.media.kind != MediaKind.AUDIO}
        if (not isinstance(self.transitions, tuple)
                or any(not isinstance(t, Transition) or t.incoming_id not in clips
                       or t.outgoing_id not in clips for t in self.transitions)
                or len({t.incoming_id for t in self.transitions}) != len(self.transitions)
                or len({t.outgoing_id for t in self.transitions}) != len(self.transitions)):
            raise ValueError("Transitions de montage invalides.")

    def transition_spans(self):
        if not self.transitions:
            return []
        clips = {clip.id: clip for clip in self.clips}
        spans = []
        for transition in self.transitions:
            outgoing = clips.get(transition.outgoing_id)
            incoming = clips.get(transition.incoming_id)
            if outgoing is not None and incoming is not None:
                span = span_for(transition, outgoing, incoming, 1 / self.fps)
                if span is not None:
                    spans.append(span)
        # Un même calque ne peut pas être fondu par deux transitions à la fois.
        ordered = []
        occupied_until = {}
        for span in sorted(spans, key=lambda item: (item.start, item.incoming.track)):
            ids = span.outgoing.id, span.incoming.id
            start = max(span.start, *(occupied_until.get(clip_id, 0) for clip_id in ids))
            if start >= span.end - 1e-8:
                continue
            ordered.append(span if start == span.start else replace(span, start=start))
            occupied_until.update(dict.fromkeys(ids, span.end))
        return ordered

    def clips_at(self, position):
        """Calques actifs du fond vers le premier plan (piste supérieure)."""
        return sorted((c for c in self.clips
                       if c.timeline_start - 1e-9 <= position < c.timeline_end - 1e-9),
                      key=lambda clip: clip.track)

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
        self.transitions = tuple(t for t in self.transitions
                                 if clip_id not in (t.incoming_id, t.outgoing_id))
