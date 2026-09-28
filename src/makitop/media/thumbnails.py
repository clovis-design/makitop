"""Génération de miniatures pour l'affichage dans le panneau médias."""

from pathlib import Path

import av
import numpy as np
from PIL import Image as PilImage

from makitop.model.media import Image, Media, Video

THUMB_W = 120
THUMB_H = 68

_PLACEHOLDER_COLOR = (0.15, 0.15, 0.18, 1.0)  # gris foncé RGBA


def generate(media: Media) -> list[float]:
    if isinstance(media, Video):
        return _from_video(media.path)
    if isinstance(media, Image):
        return _from_image(media.path)
    return _placeholder()


def _from_video(path: Path) -> list[float]:
    try:
        with av.open(str(path)) as container:
            stream = next(
                (
                    s
                    for s in container.streams.video
                    if not s.disposition & av.stream.Disposition.attached_pic
                ),
                None,
            )
            if stream is None:
                return _placeholder()
            for frame in container.decode(stream):
                return _pil_to_texture(frame.to_image())
    except Exception:
        pass
    return _placeholder()


def _from_image(path: Path) -> list[float]:
    try:
        with PilImage.open(path) as img:
            return _pil_to_texture(img)
    except Exception:
        pass
    return _placeholder()


def _pil_to_texture(img: PilImage.Image) -> list[float]:
    img = img.convert("RGBA").resize((THUMB_W, THUMB_H), PilImage.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    return arr.flatten().tolist()


def _placeholder() -> list[float]:
    arr = np.full((THUMB_H, THUMB_W, 4), _PLACEHOLDER_COLOR, dtype=np.float32)
    return arr.flatten().tolist()
