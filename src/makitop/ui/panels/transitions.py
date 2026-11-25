"""Catalogue des transitions, illustré avec le même moteur que l’export."""

from functools import cache

import cv2
import dearpygui.dearpygui as dpg
import numpy as np

from makitop.engine.transitions import blend, is_available
from makitop.model.transitions import GROUPS
from makitop.ui.assets.style import COLORS
from makitop.ui.panels.catalog_grid import COLUMNS, THUMB_H, THUMB_W, TILE_THEME, load_theme

REGISTRY = "transition_texture_registry"
FILTER = "transition_category"
_ALL = "Toutes les familles"
_on_apply = None


def bind(on_apply):
    global _on_apply
    _on_apply = on_apply


def button_tag(kind):
    return f"transition_preset_{kind}"


def _texture_tag(kind):
    return f"transition_texture_{kind}"


def _group_tag(index):
    return f"transition_family_{index}"


@cache
def thumbnail(kind):
    a = np.full((THUMB_H, THUMB_W, 4), (31, 72, 137, 255), np.uint8)
    b = np.full_like(a, 255)
    b[..., :3] = (143, 45, 89)
    cv2.circle(a, (23, 19), 10, (126, 222, 255, 255), -1, cv2.LINE_AA)
    cv2.fillConvexPoly(b, np.array(((37, 36), (61, 9), (76, 36)), np.int32),
                       (255, 185, 113, 255), cv2.LINE_AA)
    pixels = blend(a, b, kind, 0.44)
    return pixels.astype(np.float32).ravel() / 255


def build():
    load_theme()
    groups = [(title, [(kind, label) for kind, label in specs.items() if is_available(kind)])
              for title, specs in GROUPS.items()]
    groups = [(title, items) for title, items in groups if items]
    if not dpg.does_item_exist(REGISTRY):
        with dpg.texture_registry(tag=REGISTRY):
            for _, items in groups:
                for kind, _ in items:
                    dpg.add_static_texture(THUMB_W, THUMB_H, thumbnail(kind),
                                           tag=_texture_tag(kind))
    dpg.add_text("Sélectionnez le clip d’arrivée dans la timeline, puis une transition.",
                 wrap=0, color=COLORS["label_muted"])
    dpg.add_combo([_ALL, *(title for title, _ in groups)], tag=FILTER,
                  default_value=_ALL, width=-1, callback=_filter, user_data=groups)
    for index, (title, items) in enumerate(groups):
        with dpg.group(tag=_group_tag(index)):
            dpg.add_spacer(height=4)
            dpg.add_text(title)
            with dpg.table(header_row=False) as table:
                for _ in range(COLUMNS):
                    dpg.add_table_column()
                for start in range(0, len(items), COLUMNS):
                    with dpg.table_row():
                        for kind, label in items[start:start + COLUMNS]:
                            _tile(kind, label)
            dpg.bind_item_theme(table, TILE_THEME)


def _tile(kind, label):
    with dpg.table_cell():
        dpg.add_image_button(_texture_tag(kind), tag=button_tag(kind), width=THUMB_W,
                             height=THUMB_H, callback=_clicked, user_data=kind)
        with dpg.tooltip(button_tag(kind)):
            dpg.add_text(label)
        dpg.add_text(label, wrap=THUMB_W)


def _filter(sender, choice, groups):
    for index, (title, _) in enumerate(groups):
        dpg.configure_item(_group_tag(index), show=choice in (_ALL, title))


def _clicked(sender, app_data, kind):
    if _on_apply is not None:
        _on_apply(kind)
