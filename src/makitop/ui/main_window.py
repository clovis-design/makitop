"""Fenêtre principale : barre de menus + 4 zones (médias, preview, propriétés, timeline)."""

import dearpygui.dearpygui as dpg

from makitop.ui import menu_bar
from makitop.ui.layout import compute_layout
from makitop.ui.panels import media, preview, properties, timeline

ROOT = "main_window"


def build() -> None:
    with dpg.window(tag=ROOT, no_title_bar=True, no_move=True, no_resize=True):
        menu_bar.create()
        with dpg.group(horizontal=True):
            media.create()
            preview.create()
            properties.create()
        timeline.create()


def resize(width: int, height: int) -> None:
    layout = compute_layout(width, height)
    for tag, size in (
        (media.TAG, layout.media),
        (preview.TAG, layout.preview),
        (properties.TAG, layout.properties),
        (timeline.TAG, layout.timeline),
    ):
        dpg.configure_item(tag, width=size.width, height=size.height)
