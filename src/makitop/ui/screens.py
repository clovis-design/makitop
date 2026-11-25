"""Bascule entre les deux écrans de l'application : la page d'accueil et l'éditeur."""

import dearpygui.dearpygui as dpg

from makitop.ui import home, main_window, title_bar


def show_home() -> None:
    main_window.set_fullscreen(False)
    dpg.hide_item(main_window.ROOT)
    dpg.show_item(home.TAG)
    dpg.set_primary_window(home.TAG, True)
    title_bar.show_menus(False)  # l'accueil a ses propres boutons
    resize()


def show_editor() -> None:
    dpg.hide_item(home.TAG)
    dpg.show_item(main_window.ROOT)
    dpg.set_primary_window(main_window.ROOT, True)
    title_bar.show_menus(True)
    resize()


def home_shown() -> bool:
    return dpg.is_item_shown(home.TAG)


def resize() -> None:
    """Adapte l'écran affiché à la taille de la fenêtre."""
    if not dpg.is_viewport_ok():  # pas de viewport dans les tests
        return
    width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
    title_bar.resize(width, height)
    if home_shown():
        home.resize(width, height)
    else:
        main_window.resize(width, height)
