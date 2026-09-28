"""Barre de navigation verticale à gauche : choisit la section du panneau médias."""

import dearpygui.dearpygui as dpg

from makitop.ui.panels import media

TAG = "sidebar_panel"
SELECTED_THEME = "sidebar_selected_theme"

# Libellés courts des boutons (la barre est étroite).
LABELS: dict[str, str] = {
    "imports": "Médias",
    "video_effects": "Vidéo",
    "audio_effects": "Audio",
    "text": "Texte",
    "transitions": "Transit.",
}


def button_tag(key: str) -> str:
    return f"sidebar_button_{key}"


def create() -> None:
    with dpg.theme(tag=SELECTED_THEME), dpg.theme_component(dpg.mvButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (41, 74, 122))

    with dpg.child_window(tag=TAG, border=True, no_scrollbar=True):
        for key, title in media.SECTIONS:
            dpg.add_button(
                tag=button_tag(key),
                label=LABELS.get(key, title),
                width=-1,
                height=48,
                callback=_on_click,
                user_data=key,
            )
            with dpg.tooltip(button_tag(key)):
                dpg.add_text(title)


def select(key: str) -> None:
    _highlight(key)
    media.show_section(key)


def _highlight(key: str) -> None:
    for other, _ in media.SECTIONS:
        dpg.bind_item_theme(button_tag(other), SELECTED_THEME if other == key else 0)


def _on_click(sender, app_data, user_data: str) -> None:
    select(user_data)
