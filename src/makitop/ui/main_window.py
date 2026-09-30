"""Fenêtre principale : menus, navigation, médias, preview, propriétés, timeline."""

from collections.abc import Callable

import dearpygui.dearpygui as dpg

from makitop.ui import menu_bar, shortcuts
from makitop.ui.layout import compute_layout
from makitop.ui.panels import media, preview, properties, sidebar, timeline

ROOT = "main_window"


def build(actions: dict[str, Callable[[], None]] | None = None) -> None:
    """`actions` associe un libellé de menu (voir menu_bar.MENUS) à la fonction à appeler.
    Les raccourcis clavier (ui/shortcuts.py) déclenchent les mêmes actions."""
    actions = actions or {}
    shortcuts.install(actions)
    with dpg.window(tag=ROOT, no_title_bar=True, no_move=True, no_resize=True):
        menu_bar.create(actions, shortcuts.labels())
        with dpg.group(horizontal=True):
            sidebar.create()
            media.create()
            with dpg.group():
                with dpg.group(horizontal=True):
                    preview.create()
                    properties.create()
                timeline.create()
    sidebar.select(media.DEFAULT_SECTION)


def resize(width: int, height: int) -> None:
    layout = compute_layout(width, height)
    for tag, size in (
        (sidebar.TAG, layout.sidebar),
        (media.TAG, layout.media),
        (preview.TAG, layout.preview),
        (properties.TAG, layout.properties),
        (timeline.TAG, layout.timeline),
    ):
        dpg.configure_item(tag, width=size.width, height=size.height)
