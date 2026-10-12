"""Géométrie normalisée du cadre et de ses calques, indépendante de l'interface."""

import math
from dataclasses import dataclass, replace

FORMATS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}


@dataclass(frozen=True)
class Transform:
    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0
    crop_left: float = 0.0
    crop_top: float = 0.0
    crop_right: float = 0.0
    crop_bottom: float = 0.0

    def __post_init__(self):
        values = vars(self).values()
        if not all(math.isfinite(v) for v in values):
            raise ValueError("La géométrie doit contenir des valeurs finies.")
        if not (0 < self.width <= 8 and 0 < self.height <= 8):
            raise ValueError("Taille de calque invalide.")
        if abs(self.x) > 8 or abs(self.y) > 8:
            raise ValueError("Position de calque invalide.")
        crops = (self.crop_left, self.crop_top, self.crop_right, self.crop_bottom)
        if any(c < 0 for c in crops) or (
            self.crop_left + self.crop_right >= 0.99
            or self.crop_top + self.crop_bottom >= 0.99
        ):
            raise ValueError("Le recadrage doit conserver une partie visible de l'image.")


def fitted_bounds(transform, media_width, media_height, canvas_ratio):
    """Rectangle visible (x, y, largeur, hauteur), sans déformation de la source."""
    t = transform
    ratio = ((media_width or 1) * (1 - t.crop_left - t.crop_right)
             / ((media_height or 1) * (1 - t.crop_top - t.crop_bottom)))
    width = min(t.width, t.height * ratio / canvas_ratio)
    height = width * canvas_ratio / ratio
    return t.x + (t.width - width) / 2, t.y + (t.height - height) / 2, width, height


def drag_transform(original, bounds, mode, handle, dx, dy, canvas_ratio):
    """Un geste souris total depuis son origine ; les coins conservent les proportions."""
    x, y, width, height = bounds
    t = replace(original, x=x, y=y, width=width, height=height)
    if handle == "move":
        return replace(t, x=max(-8, min(8, x + dx)), y=max(-8, min(8, y + dy)))
    if mode == "crop":
        full_w = width / (1 - t.crop_left - t.crop_right)
        full_h = height / (1 - t.crop_top - t.crop_bottom)
        if handle in ("left", "right"):
            sign = 1 if handle == "left" else -1
            field = f"crop_{handle}"
            change = max(-getattr(t, field), min(
                sign * dx / full_w, 0.98 - t.crop_left - t.crop_right,
            ))
            return replace(t, **{field: getattr(t, field) + change},
                           x=x + (change * full_w if handle == "left" else 0),
                           width=width - change * full_w)
        sign = 1 if handle == "top" else -1
        field = f"crop_{handle}"
        change = max(-getattr(t, field), min(
            sign * dy / full_h, 0.98 - t.crop_top - t.crop_bottom,
        ))
        return replace(t, **{field: getattr(t, field) + change},
                       y=y + (change * full_h if handle == "top" else 0),
                       height=height - change * full_h)
    sx = -1 if "left" in handle else 1
    sy = -1 if "top" in handle else 1
    scale = 1 + (sx * dx * width * canvas_ratio**2 + sy * dy * height) / (
        (width * canvas_ratio)**2 + height**2
    )
    scale = max(0.02 / min(width, height), min(scale, 8 / max(width, height)))
    new_w, new_h = width * scale, height * scale
    return replace(t, x=x + (width - new_w if sx < 0 else 0),
                   y=y + (height - new_h if sy < 0 else 0), width=new_w, height=new_h)
