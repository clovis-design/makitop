"""Zone « Preview » : lecteur vidéo (texture alimentée par render(t))."""

import dearpygui.dearpygui as dpg

TAG = "preview_panel"


def create() -> None:
    with dpg.child_window(tag=TAG, border=True):
        dpg.add_text("Preview")
        dpg.add_separator()
