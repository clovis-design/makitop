"""Catalogue de préréglages de texte présenté en vignettes typographiques."""

from collections.abc import Callable

import dearpygui.dearpygui as dpg
import numpy as np
from PIL import Image, ImageDraw

from makitop.engine.text import load_font
from makitop.model.text import FONTS, PRESETS
from makitop.ui.assets.style import COLORS
from makitop.ui.panels import catalog_grid
from makitop.ui.panels.catalog_grid import THUMB_H, THUMB_W

REGISTRY = "text_preset_texture_registry"
_GHOST_TAG = "text_preset_drag_ghost"
_GHOST_TEXT_TAG = "text_preset_drag_ghost_label"

_drag_candidate: str | None = None
_drag_start_pos: tuple | None = None
_drag_active: bool = False
_dragging_text: str | None = None


def get_dragging_text() -> str | None:
    return _dragging_text if _drag_active else None


def _ensure_ghost() -> None:
    if dpg.does_item_exist(_GHOST_TAG):
        return
    with dpg.window(
        tag=_GHOST_TAG,
        no_title_bar=True, no_resize=True, no_move=True,
        no_scrollbar=True, no_collapse=True, no_saved_settings=True,
        no_focus_on_appearing=True, no_background=True,
        autosize=True, show=False, min_size=[1, 1],
    ):
        dpg.add_text("", tag=_GHOST_TEXT_TAG, color=COLORS["text_main"])


def tick() -> None:
    global _drag_candidate, _drag_start_pos, _drag_active, _dragging_text
    _ensure_ghost()
    btn = dpg.is_mouse_button_down(dpg.mvMouseButton_Left)
    if not _drag_candidate:
        for kind in PRESETS:
            tag = button_tag(kind)
            if dpg.does_item_exist(tag) and dpg.is_item_active(tag):
                _drag_candidate = kind
                _drag_start_pos = dpg.get_mouse_pos(local=False)
                break
    if btn and _drag_candidate and not _drag_active and _drag_start_pos:
        pos = dpg.get_mouse_pos(local=False)
        if abs(pos[0] - _drag_start_pos[0]) > 5 or abs(pos[1] - _drag_start_pos[1]) > 5:
            _drag_active = True
            _dragging_text = _drag_candidate
    if _drag_active and _dragging_text and dpg.does_item_exist(_GHOST_TAG):
        pos = dpg.get_mouse_pos(local=False)
        dpg.set_value(_GHOST_TEXT_TAG, PRESETS[_dragging_text].label)
        dpg.configure_item(_GHOST_TAG, pos=(int(pos[0]) + 16, int(pos[1]) + 16), show=True)
        dpg.focus_item(_GHOST_TAG)
    elif dpg.does_item_exist(_GHOST_TAG):
        dpg.configure_item(_GHOST_TAG, show=False)
    if not btn:
        _drag_candidate = None
        _drag_start_pos = None
        _drag_active = False
        _dragging_text = None
GROUPS = {
    "Titres": ("title", "heading", "subtitle"),
    "Corps de texte": ("paragraph", "quote", "caption"),
    "Habillage": ("lower_third", "chapter", "credits"),
    "Styles typographiques": ("editorial", "elegant", "terminal"),
}

_SCALE = 3
_ACCENT = (188, 161, 245)
_MUTED = (148, 150, 187)
# Position, texte, taille et point d'ancrage sur la vignette.
_GLYPHS = {
    "title": ((42, 23, "Aa", 25, "mm"),),
    "heading": ((42, 18, "Aa", 19, "mm"),),
    "subtitle": ((42, 35, "Abc", 11, "mm"),),
    "paragraph": ((14, 12, "A", 13, "lm"),),
    "quote": ((42, 20, "« »", 27, "mm"),),
    "caption": ((70, 35, "01", 12, "rm"),),
    "lower_third": ((15, 29, "Nom", 12, "lm"),),
    "chapter": ((24, 23, "01", 19, "mm"), (48, 23, "Aa", 13, "lm")),
    "credits": ((42, 12, "FIN", 11, "mm"),),
    "editorial": ((42, 22, "Aa", 26, "mm"),),
    "elegant": ((42, 22, "Aa", 26, "mm"),),
    "terminal": ((11, 19, "> Aa", 16, "lm"),),
}
_LINES = {
    "heading": ((28, 32, 56),),
    "paragraph": ((27, 13, 69), (14, 22, 69), (14, 30, 61), (14, 37, 48)),
    "quote": ((34, 35, 50),),
    "caption": ((51, 25, 69),),
    "lower_third": ((15, 39, 39),),
    "credits": ((25, 23, 59), (30, 29, 54), (27, 35, 57)),
    "terminal": ((13, 33, 44), (13, 38, 34)),
}


def button_tag(kind: str) -> str:
    return f"text_preset_{kind}"


def texture_tag(kind: str) -> str:
    return f"text_preset_texture_{kind}"


def thumbnail(kind: str) -> np.ndarray:
    style = PRESETS[kind].style
    image = Image.new("RGBA", (THUMB_W * _SCALE, THUMB_H * _SCALE))
    draw = ImageDraw.Draw(image)

    def coords(*values):
        return tuple(value * _SCALE for value in values)

    def line(x0, y0, x1, y1, color):
        draw.line(coords(x0, y0, x1, y1), fill=color, width=_SCALE)

    draw.rounded_rectangle(
        (0, 0, image.width - 1, image.height - 1), radius=6 * _SCALE,
        fill=(28, 27, 56), outline=(68, 60, 106), width=_SCALE,
    )
    if kind == "subtitle":
        draw.rounded_rectangle(coords(22, 27, 62, 42), radius=3 * _SCALE,
                               fill=(58, 45, 93))
    if kind == "lower_third":
        line(10, 23, 10, 40, _ACCENT)
    if kind == "chapter":
        line(41, 15, 41, 31, _MUTED)
    for x, y, end in _LINES.get(kind, ()):
        line(x, y, end, y, _MUTED)
    for x, y, text, size, anchor in _GLYPHS[kind]:
        draw.text(coords(x, y), text, font=load_font(style.font, size * _SCALE, style.bold),
                  anchor=anchor, fill=style.color)
    pixels = np.asarray(image.resize((THUMB_W, THUMB_H), Image.Resampling.LANCZOS),
                        dtype=np.float32)
    return pixels.ravel() / 255


def _load_textures() -> None:
    if dpg.does_alias_exist(REGISTRY):
        return
    with dpg.texture_registry(tag=REGISTRY):
        for kind in PRESETS:
            dpg.add_static_texture(THUMB_W, THUMB_H, thumbnail(kind), tag=texture_tag(kind))


def build(on_add: Callable[[str], None] | None) -> None:
    _load_textures()
    dpg.add_text("Cliquez sur un modèle pour l’ajouter à la tête de lecture.",
                 wrap=0, color=COLORS["label_muted"])

    def clicked(sender, app_data, kind):
        if on_add is not None:
            on_add(kind)

    def add_tile(kind):
        preset = PRESETS[kind]
        font_name = next(label for label, font in FONTS.items() if font == preset.style.font)
        description = f"{preset.description}\nPolice : {font_name}"
        catalog_grid.tile(button_tag(kind), texture_tag(kind), preset.label, description,
                          clicked, kind, enabled=on_add is not None)

    for title, kinds in GROUPS.items():
        catalog_grid.section(title, kinds, add_tile)
