"""Génération de miniatures pour l'affichage dans le panneau médias."""

from pathlib import Path

import av
import numpy as np
from PIL import Image as PilImage

from makitop.model.media import Media, MediaKind

THUMB_W = 160
THUMB_H = 90

_PLACEHOLDER_COLOR = (0.15, 0.15, 0.18, 1.0)  # gris foncé RGBA


def generate(media: Media) -> list[float]:
    if media.kind is MediaKind.VIDEO:
        return _from_video(media.path)
    if media.kind is MediaKind.IMAGE:
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
    img = img.convert("RGBA")
    w, h = img.size
    scale = min(THUMB_W / w, THUMB_H / h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), PilImage.LANCZOS)

    canvas = PilImage.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 255))
    offset_x = (THUMB_W - new_w) // 2
    offset_y = (THUMB_H - new_h) // 2
    canvas.paste(img, (offset_x, offset_y))

    arr = np.array(canvas, dtype=np.float32) / 255.0
    return arr.flatten().tolist()


def _placeholder() -> list[float]:
    arr = np.full((THUMB_H, THUMB_W, 4), _PLACEHOLDER_COLOR, dtype=np.float32)
    return arr.flatten().tolist()
