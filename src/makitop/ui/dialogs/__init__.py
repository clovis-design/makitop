"""Boîtes de dialogue Dear PyGui : import, export et paramètres du projet."""

import dearpygui.dearpygui as dpg


def center_window(tag, width: int, height: int) -> None:
    """Positionne une fenêtre au centre du viewport d'après ses dimensions connues."""
    if not dpg.is_viewport_ok():
        return
    vw = dpg.get_viewport_client_width()
    vh = dpg.get_viewport_client_height()
    dpg.set_item_pos(tag, [max((vw - width) // 2, 0), max((vh - height) // 2, 0)])
