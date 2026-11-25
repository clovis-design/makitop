"""Icônes de la barre d'outils de la timeline (copier, coller, couper…), dessinées en numpy."""

import dearpygui.dearpygui as dpg
import numpy as np

from makitop.ui.panels.transport_icons import _rect, _triangle, icon_rgba

ICON_SIZE = 16
NAMES = ("zoom_out", "zoom_in", "copy", "paste", "cut", "duplicate", "delete", "split",
         "undo", "redo", "keyframes")
REGISTRY = "timeline_texture_registry"
_STROKE = 0.09


def texture_tag(name: str) -> str:
    return f"timeline_texture_{name}"


def _frame(x, y, x0, y0, x1, y1, t=_STROKE):
    """Contour de rectangle d'épaisseur t."""
    return _rect(x, y, x0, y0, x1, y1) & ~_rect(x, y, x0 + t, y0 + t, x1 - t, y1 - t)


def _segment(x, y, p, q, w):
    """Trait de demi-épaisseur w entre p et q."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    t = np.clip(((x - p[0]) * dx + (y - p[1]) * dy) / (dx * dx + dy * dy), 0, 1)
    return np.hypot(x - (p[0] + t * dx), y - (p[1] + t * dy)) < w


def _two_sheets(x, y):
    """Feuille avant en bas à droite, feuille arrière visible en haut à gauche."""
    front = _frame(x, y, 0.36, 0.36, 0.88, 0.88)
    back = _frame(x, y, 0.12, 0.12, 0.64, 0.64) & ~_rect(x, y, 0.28, 0.28, 0.92, 0.92)
    return front | back


def _mask(name, x, y):
    """Forme de l'icône en coordonnées normalisées [0, 1] (y vers le bas)."""
    if name in ("zoom_in", "zoom_out"):
        # Loupe ; le signe est centré sur le pixel 6 pour rester net.
        c = 0.40625
        radius = np.hypot(x - c, y - c)
        lens = (radius > 0.21) & (radius < 0.31)
        handle = _segment(x, y, (0.63, 0.63), (0.9, 0.9), 0.08)
        sign = _rect(x, y, 0.3125, 0.375, 0.5, 0.4375)
        if name == "zoom_in":
            sign |= _rect(x, y, 0.375, 0.3125, 0.4375, 0.5)
        return lens | handle | sign
    if name == "keyframes":
        # Image clé (losange) posée sur une piste.
        diamond = np.abs(x - 0.5) + np.abs(y - 0.5) < 0.3
        track = (_rect(x, y, 0.02, 0.4375, 0.16, 0.5625)
                 | _rect(x, y, 0.84, 0.4375, 0.98, 0.5625))
        return diamond | track
    if name == "copy":
        return _two_sheets(x, y)
    if name == "duplicate":
        # « + » de 3 px aligné sur la grille de 16 px pour rester net.
        plus = (_rect(x, y, 0.5625, 0.625, 0.75, 0.6875)
                | _rect(x, y, 0.625, 0.5625, 0.6875, 0.75))
        return _two_sheets(x, y) | plus
    if name == "paste":
        board = _frame(x, y, 0.18, 0.18, 0.82, 0.92)
        tab = _rect(x, y, 0.36, 0.08, 0.64, 0.28)
        lines = _rect(x, y, 0.34, 0.46, 0.66, 0.54) | _rect(x, y, 0.34, 0.64, 0.58, 0.72)
        return board | tab | lines
    if name == "cut":
        def ring(cx):
            r = np.hypot(x - cx, y - 0.76)
            return (r > 0.08) & (r < 0.17)
        blades = (_segment(x, y, (0.38, 0.62), (0.74, 0.08), 0.055)
                  | _segment(x, y, (0.62, 0.62), (0.26, 0.08), 0.055))
        return ring(0.28) | ring(0.72) | blades
    if name == "delete":
        handle = _frame(x, y, 0.38, 0.06, 0.62, 0.26) & (y < 0.2)
        lid = _rect(x, y, 0.12, 0.2, 0.88, 0.29)
        # Parois et fentes alignées sur la grille de 16 px pour rester nettes.
        body = (_rect(x, y, 0.1875, 0.35, 0.8125, 0.9375)
                & ~_rect(x, y, 0.3125, 0.3, 0.6875, 0.8125))
        slits = (_rect(x, y, 0.375, 0.4375, 0.4375, 0.75)
                 | _rect(x, y, 0.5625, 0.4375, 0.625, 0.75))
        return handle | lid | body | slits
    if name == "split":
        clips = _rect(x, y, 0.04, 0.4, 0.38, 0.84) | _rect(x, y, 0.62, 0.4, 0.96, 0.84)
        blade = _rect(x, y, 0.46, 0.2, 0.54, 0.96)
        head = _triangle(x, y, (0.28, 0.04), (0.72, 0.04), (0.5, 0.28))
        return clips | blade | head
    if name == "undo":
        # Demi-cercle supérieur, terminé à gauche par une pointe tournée vers le bas.
        radius = np.hypot(x - 0.56, y - 0.64)
        arc = (radius > 0.2) & (radius < 0.31) & (y <= 0.64)
        return arc | _triangle(x, y, (0.08, 0.56), (0.52, 0.56), (0.3, 0.86))
    if name == "redo":
        return _mask("undo", 1 - x, y)
    raise KeyError(name)


def load_textures() -> None:
    if dpg.does_alias_exist(REGISTRY):
        return
    with dpg.texture_registry(tag=REGISTRY):
        for name in NAMES:
            dpg.add_static_texture(width=ICON_SIZE, height=ICON_SIZE,
                                   default_value=icon_rgba(name, ICON_SIZE, _mask),
                                   tag=texture_tag(name))
