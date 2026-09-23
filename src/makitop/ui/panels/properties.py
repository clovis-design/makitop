"""Zone « Propriétés » : réglages du clip, de l'effet ou du keyframe sélectionné."""

import dearpygui.dearpygui as dpg

TAG = "properties_panel"


def create() -> None:
    with dpg.child_window(tag=TAG, border=True):
        dpg.add_text("Propriétés")
        dpg.add_separator()
