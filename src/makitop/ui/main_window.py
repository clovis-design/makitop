"""Fenêtre principale : menus, navigation, médias, preview, propriétés, timeline."""

import os
from collections.abc import Callable

import dearpygui.dearpygui as dpg

from makitop.ui import menu_bar
from makitop.ui.layout import compute_layout
from makitop.ui.panels import media, preview, properties, sidebar, timeline
from makitop.ui.assets.style import COLORS, FONT_INTER

ROOT = "main_window"

def apply_global_style() -> None:
    """Applique les couleurs et la police globales à toute l'interface."""
    
    # 1. Gestion des couleurs (Thème)
    with dpg.theme() as main_theme:
        with dpg.theme_component(dpg.mvWindowAppItem):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLORS["bg_panel"])
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)
            
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_main"])
            
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text_main"])
            
    dpg.bind_item_theme(ROOT, main_theme)

    # 2. Gestion de la police globale
    if os.path.exists(FONT_INTER):
        with dpg.font_registry():
            # Charge la police à la taille 16 depuis la constante de style.py
            default_font = dpg.add_font(FONT_INTER, 16)
        
        # dpg.bind_font SANS cible applique cette police à toute l'application !
        dpg.bind_font(default_font)
    else:
        print(f"Attention : Fichier de police introuvable -> {FONT_INTER}")


def build(actions: dict[str, Callable[[], None]] | None = None) -> None:
    """`actions` associe un libellé de menu (voir menu_bar.MENUS) à la fonction à appeler."""
    with dpg.window(tag=ROOT, no_title_bar=True, no_move=True, no_resize=True):
        menu_bar.create(actions)
        with dpg.group(horizontal=True):
            sidebar.create()
            media.create()
            with dpg.group():
                with dpg.group(horizontal=True):
                    preview.create()
                    properties.create()
                timeline.create()
    apply_global_style()
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
