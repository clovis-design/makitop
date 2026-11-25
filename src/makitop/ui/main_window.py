"""Fenêtre principale : menus, navigation, médias, preview, propriétés, timeline."""

import os
from collections.abc import Callable

import dearpygui.dearpygui as dpg

from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.model.media import Media
from makitop.ui import menu_bar, shortcuts, title_bar
from makitop.ui.assets.style import COLORS, FONT_INTER
from makitop.ui.layout import TITLE_BAR_HEIGHT, V_SPACING, compute_layout
from makitop.ui.panels import media, preview, properties, sidebar, timeline

ROOT = "main_window"
TOP_ROW = "main_top_row"
FULLSCREEN_WINDOW = "fullscreen_window"
FULLSCREEN_THEME = "fullscreen_theme"

_fullscreen = False

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

    with dpg.theme(tag=FULLSCREEN_THEME):
        with dpg.theme_component(dpg.mvWindowAppItem):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLORS["viewer_bg"])
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_main"])
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text_main"])
    dpg.bind_item_theme(FULLSCREEN_WINDOW, FULLSCREEN_THEME)

def setup_fonts() -> None:
    """Charge les polices en mémoire AVANT la construction de l'interface."""
    if os.path.exists(FONT_INTER):
        if not dpg.does_alias_exist("font_registry"):
            dpg.add_font_registry(tag="font_registry")
            
        with dpg.font_registry():
            default_font = dpg.add_font(FONT_INTER, 16)
            # Taille 10 est souvent plus lisible que 8 pour les petits écrans
            dpg.add_font(FONT_INTER, 15, tag="small_text_font")
            dpg.add_font(FONT_INTER, 19, tag="timecode_font")
            
        dpg.bind_font(default_font)
    else:
        print(f"Attention : Fichier de police introuvable -> {FONT_INTER}")

def build(
    actions: dict[str, Callable[[], None]] | None = None,
    playback_controller: TimelinePlaybackController | None = None,
    on_media_selected: Callable[[Media], None] | None = None,
    on_add_to_timeline: Callable[[Media], None] | None = None,
    block_shortcuts: Callable[[], bool] | None = None,
    on_add_text: Callable[[str], None] | None = None,
    on_close: Callable[[], None] | None = None,
) -> None:
    """`actions` associe un libellé de menu (voir menu_bar.MENUS) à la fonction à appeler.
    Les raccourcis clavier (ui/shortcuts.py) déclenchent les mêmes actions.
    Les menus sont dans la barre de titre (ui/title_bar.py), dont `on_close` est le bouton ✕."""
    global _fullscreen
    _fullscreen = False
    actions = actions or {}
    shortcuts.install(actions, blocked=block_shortcuts)
    preview.create_video_texture()
    setup_fonts()
    with dpg.window(tag=ROOT, no_title_bar=True, no_move=True, no_resize=True):
        # Place de la barre de titre, posée par-dessus cette fenêtre.
        dpg.add_spacer(height=TITLE_BAR_HEIGHT - V_SPACING)
        with dpg.group(horizontal=True):
            sidebar.create()
            media.create(on_media_selected, actions.get(menu_bar.IMPORT_MEDIA), on_add_to_timeline,
                         on_add_text=on_add_text)
            with dpg.group():
                with dpg.group(horizontal=True, tag=TOP_ROW):
                    preview.create(playback=playback_controller,
                                   on_toggle_fullscreen=toggle_fullscreen)
                    properties.create()
                timeline.create()
    # Fenêtre du plein écran : le panneau preview y est déplacé tel quel (voir set_fullscreen).
    with dpg.window(tag=FULLSCREEN_WINDOW, no_title_bar=True, no_move=True, no_resize=True,
                    no_scrollbar=True, show=False):
        pass
    title_bar.create(actions, shortcuts.labels(), on_close)
    apply_global_style()
    sidebar.select(media.DEFAULT_SECTION)


def is_fullscreen() -> bool:
    return _fullscreen


def toggle_fullscreen() -> None:
    set_fullscreen(not _fullscreen)


def set_fullscreen(on: bool) -> None:
    """Plein écran du viewer : seul le panneau preview reste, sur tout l'écran."""
    global _fullscreen
    if on == _fullscreen:
        return
    _fullscreen = on
    if on:
        dpg.move_item(preview.TAG, parent=FULLSCREEN_WINDOW)
        dpg.hide_item(ROOT)
        dpg.show_item(FULLSCREEN_WINDOW)
        dpg.set_primary_window(FULLSCREEN_WINDOW, True)
    else:
        dpg.move_item(preview.TAG, parent=TOP_ROW, before=properties.TAG)
        dpg.hide_item(FULLSCREEN_WINDOW)
        dpg.show_item(ROOT)
        dpg.set_primary_window(ROOT, True)
    preview.set_fullscreen(on)
    title_bar.set_visible(not on)
    if dpg.is_viewport_ok():  # pas de viewport dans les tests
        dpg.toggle_viewport_fullscreen()
        resize(dpg.get_viewport_client_width(), dpg.get_viewport_client_height())


def resize(width: int, height: int) -> None:
    if _fullscreen:
        dpg.configure_item(preview.TAG, width=width, height=height)
        preview.resize(width, height)
        return
    layout = compute_layout(width, height)
    for tag, size in (
        (sidebar.TAG, layout.sidebar),
        (media.TAG, layout.media),
        (preview.TAG, layout.preview),
        (properties.TAG, layout.properties),
        (timeline.TAG, layout.timeline),
    ):
        dpg.configure_item(tag, width=size.width, height=size.height)
    preview.resize(layout.preview.width, layout.preview.height)
