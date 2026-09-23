"""Zone « Médias » : media browser, liste des fichiers importés."""

import dearpygui.dearpygui as dpg

TAG = "media_panel"


def create() -> None:
    with dpg.child_window(tag=TAG, border=True):
        dpg.add_text("Médias")
        dpg.add_separator()
