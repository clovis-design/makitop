"""Fenêtre principale : menus, navigation, médias, preview, propriétés, timeline."""

import dearpygui.dearpygui as dpg

from makitop.ui import menu_bar
from makitop.ui.layout import compute_layout
from makitop.ui.panels import media, preview, properties, sidebar, timeline
from makitop.ui.assets.style import COLORS, FONT_INTER

ROOT = "main_window"

def apply_main_background() -> None:
    """Applique une couleur de fond uniquement à la fenêtre racine."""
    with dpg.theme() as main_theme:
        # On cible EXPLICITEMENT les fenêtres classiques, pas les child_windows
        with dpg.theme_component(dpg.mvWindowAppItem):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLORS["bg_panel"])
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)
            
    # On lie ce thème uniquement à ROOT
    dpg.bind_item_theme(ROOT, main_theme)

def build() -> None:
    with dpg.window(tag=ROOT, no_title_bar=True, no_move=True, no_resize=True):
        menu_bar.create()
        with dpg.group(horizontal=True):
            sidebar.create()
            media.create()
            with dpg.group():
                with dpg.group(horizontal=True):
                    preview.create()
                    properties.create()
                timeline.create()

    apply_main_background()
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
