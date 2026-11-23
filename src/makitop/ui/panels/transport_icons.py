"""Icônes de la barre de lecture (style DaVinci Resolve), dessinées en numpy."""

import dearpygui.dearpygui as dpg
import numpy as np

ICON_SIZE = 16
COLOR = (205, 205, 210)
NAMES = ("start", "stop", "play", "pause", "end", "fullscreen", "exit_fullscreen")
REGISTRY = "transport_texture_registry"
_SUPERSAMPLE = 4


def texture_tag(name: str) -> str:
    return f"transport_texture_{name}"


def _rect(x, y, x0, y0, x1, y1):
    return (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)


def _triangle(x, y, a, b, c):
    def edge(p, q):
        return (q[0] - p[0]) * (y - p[1]) - (q[1] - p[1]) * (x - p[0])
    d1, d2, d3 = edge(a, b), edge(b, c), edge(c, a)
    return ((d1 >= 0) & (d2 >= 0) & (d3 >= 0)) | ((d1 <= 0) & (d2 <= 0) & (d3 <= 0))


def _mask(name, x, y):
    """Forme de l'icône en coordonnées normalisées [0, 1] (y vers le bas)."""
    if name == "play":
        return _triangle(x, y, (0.24, 0.12), (0.24, 0.88), (0.86, 0.5))
    if name == "pause":
        return _rect(x, y, 0.22, 0.14, 0.42, 0.86) | _rect(x, y, 0.58, 0.14, 0.78, 0.86)
    if name == "stop":
        return _rect(x, y, 0.2, 0.2, 0.8, 0.8)
    if name == "start":
        return _rect(x, y, 0.16, 0.16, 0.28, 0.84) | _triangle(
            x, y, (0.84, 0.16), (0.84, 0.84), (0.3, 0.5))
    if name == "end":
        return _mask("start", 1 - x, y)
    if name in ("fullscreen", "exit_fullscreen"):
        # Une équerre par coin, symétrique : on ramène tout au coin haut gauche.
        u, v = np.minimum(x, 1 - x), np.minimum(y, 1 - y)
        if name == "fullscreen":  # équerres collées aux bords, ouvertes vers le centre
            return (_rect(u, v, 0.08, 0.08, 0.38, 0.2) | _rect(u, v, 0.08, 0.08, 0.2, 0.38))
        # Équerres tournées vers l'extérieur : leur angle pointe vers le centre.
        return (_rect(u, v, 0.08, 0.26, 0.38, 0.38) | _rect(u, v, 0.26, 0.08, 0.38, 0.38))
    raise KeyError(name)


def icon_rgba(name: str, size: int = ICON_SIZE, mask=_mask) -> np.ndarray:
    """Renvoie l'icône en RGBA flottant aplati, prête pour une texture Dear PyGui."""
    n = size * _SUPERSAMPLE
    coords = (np.arange(n) + 0.5) / n
    x, y = np.meshgrid(coords, coords)
    coverage = mask(name, x, y).reshape(size, _SUPERSAMPLE, size, _SUPERSAMPLE).mean(axis=(1, 3))
    rgba = np.empty((size, size, 4), dtype=np.float32)
    rgba[..., :3] = np.array(COLOR, dtype=np.float32) / 255
    rgba[..., 3] = coverage
    return rgba.ravel()


def load_textures() -> None:
    if dpg.does_alias_exist(REGISTRY):
        return
    with dpg.texture_registry(tag=REGISTRY):
        for name in NAMES:
            dpg.add_static_texture(width=ICON_SIZE, height=ICON_SIZE,
                                   default_value=icon_rgba(name), tag=texture_tag(name))
