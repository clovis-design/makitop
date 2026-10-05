"""Zone « Timeline » : pistes et clips (Dear PyGui Plot)."""


import dearpygui.dearpygui as dpg
import os
from makitop.ui.assets.style import COLORS, FONT_INTER

TAG = "timeline_panel"


def create() -> None:
    with dpg.child_window(tag=TAG, border=False):
        dpg.add_text("Timeline")
        dpg.add_separator()