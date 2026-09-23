"""Point d'entrée : crée le contexte Dear PyGui, construit l'interface et lance la boucle."""

import dearpygui.dearpygui as dpg

from makitop import __version__
from makitop.ui import main_window

TITLE = f"Makitop {__version__}"
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 800


def main() -> None:
    dpg.create_context()
    try:
        main_window.build()
        dpg.create_viewport(
            title=TITLE,
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            min_width=800,
            min_height=500,
        )
        dpg.set_viewport_resize_callback(lambda: main_window.resize(*_viewport_client_size()))
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window(main_window.ROOT, True)
        main_window.resize(*_viewport_client_size())
        dpg.start_dearpygui()
    finally:
        dpg.destroy_context()


def _viewport_client_size() -> tuple[int, int]:
    return dpg.get_viewport_client_width(), dpg.get_viewport_client_height()


if __name__ == "__main__":
    main()
