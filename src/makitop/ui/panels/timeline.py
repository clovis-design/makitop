"""Zone « Timeline » : pistes et clips (Dear PyGui Plot)."""

import dearpygui.dearpygui as dpg

TAG = "timeline_panel"


def create() -> None:
    with dpg.child_window(tag=TAG, border=True):
        dpg.add_text("Timeline")
        dpg.add_separator()
