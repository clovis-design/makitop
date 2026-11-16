"""Petites icônes du panneau Propriétés (style Inspecteur de DaVinci Resolve), en numpy."""

import dearpygui.dearpygui as dpg
import numpy as np

from makitop.ui.panels.transport_icons import _triangle, icon_rgba

ICON_SIZE = 14
NAMES = ("chevron_down", "chevron_right", "reset", "close")
REGISTRY = "inspector_texture_registry"


def texture_tag(name: str) -> str:
    return f"inspector_texture_{name}"


def _mask(name, x, y):
    """Forme de l'icône en coordonnées normalisées [0, 1] (y vers le bas)."""
    if name == "chevron_down":
        return _triangle(x, y, (0.2, 0.32), (0.8, 0.32), (0.5, 0.72))
    if name == "chevron_right":
        return _triangle(x, y, (0.32, 0.2), (0.32, 0.8), (0.72, 0.5))
    if name == "close":
        inside = (x > 0.2) & (x < 0.8) & (y > 0.2) & (y < 0.8)
        return inside & ((np.abs(x - y) < 0.09) | (np.abs(x + y - 1) < 0.09))
    if name == "reset":
        # Cercle ouvert en haut à droite, terminé par une flèche (sens horaire).
        radius = np.hypot(x - 0.5, y - 0.55)
        ring = (radius > 0.23) & (radius < 0.35) & ~((x > 0.5) & (y < 0.55))
        return ring | _triangle(x, y, (0.46, 0.06), (0.46, 0.44), (0.74, 0.25))
    raise KeyError(name)


def load_textures() -> None:
    if dpg.does_alias_exist(REGISTRY):
        return
    with dpg.texture_registry(tag=REGISTRY):
        for name in NAMES:
            dpg.add_static_texture(width=ICON_SIZE, height=ICON_SIZE,
                                   default_value=icon_rgba(name, ICON_SIZE, _mask),
                                   tag=texture_tag(name))
