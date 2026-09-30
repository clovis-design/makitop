"""Petite fenêtre de message (erreur d'ouverture, d'enregistrement...)."""

import dearpygui.dearpygui as dpg

TAG = "message_window"
TEXT_TAG = "message_window_text"
WIDTH = 450


def create() -> None:
    # Pas modale, pour la même raison que la fenêtre d'erreurs d'import : une fenêtre
    # modale ouverte pendant la fermeture d'un dialogue de fichiers est aussitôt refermée.
    with dpg.window(
        tag=TAG,
        label="Makitop",
        show=False,
        no_collapse=True,
        autosize=True,
    ):
        dpg.add_text("", tag=TEXT_TAG, wrap=WIDTH - 30)
        dpg.add_button(label="OK", width=WIDTH - 16, callback=lambda: dpg.hide_item(TAG))


def show(title: str, text: str) -> None:
    dpg.configure_item(TAG, label=title)
    dpg.set_value(TEXT_TAG, text)
    if dpg.is_viewport_ok():  # pas de viewport dans les tests
        x = max((dpg.get_viewport_client_width() - WIDTH) // 2, 0)
        dpg.set_item_pos(TAG, [x, dpg.get_viewport_client_height() // 3])
    dpg.show_item(TAG)
    dpg.focus_item(TAG)
