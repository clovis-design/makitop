"""Barre de navigation verticale à gauche : choisit la section du panneau médias."""

import dearpygui.dearpygui as dpg
from pathlib import Path

from makitop.ui.panels import media

TAG = "sidebar_panel"
SELECTED_THEME = "sidebar_selected_theme"

_ROOT_DIR = Path(__file__).resolve().parents[1]
ICONS_DIR = _ROOT_DIR / "assets" / "icons"

# Libellés courts des boutons (la barre est étroite).
ICON_FILES: dict[str, str] = {
    "imports": "media.png",
    "bibliotheque": "bibliotheque.png",
    "text": "texte.png",
    "transitions": "transition.png",
}


def button_tag(key: str) -> str:
    return f"sidebar_button_{key}"


def texture_tag(key: str) -> str:
    return f"sidebar_texture_{key}"

def load_icon_textures() -> None:
    """Charge les PNG en mémoire avant la création de l'interface."""
    if not dpg.does_alias_exist("sidebar_texture_registry"):
        with dpg.texture_registry(tag="sidebar_texture_registry"):
            for key, filename in ICON_FILES.items():
                filepath = ICONS_DIR / filename
                if filepath.exists():
                    # pillow lit l'image et la convertit en données lisibles par le GPU
                    width, height, channels, data = dpg.load_image(str(filepath))
                    dpg.add_static_texture(
                        width=width, 
                        height=height, 
                        default_value=data, 
                        tag=texture_tag(key)
                    )
                else:
                    print(f"Attention : Icône introuvable -> {filepath}")


def create() -> None:
    # On s'assure que les images sont chargées avant de construire les boutons
    load_icon_textures()

    # Attention : On cible mvImageButton et plus mvButton
    # with dpg.theme(tag=SELECTED_THEME), dpg.theme_component(dpg.mvImageButton):
        # dpg.add_theme_color(dpg.mvThemeCol_Button, (41, 74, 122))

    with dpg.child_window(tag=TAG, border=True, no_scrollbar=True):
        for key, title in media.SECTIONS:
            tex_tag = texture_tag(key)
            
            # Si l'image a bien été chargée dans le registre
            if dpg.does_alias_exist(tex_tag):
                dpg.add_image_button(
                    texture_tag=tex_tag,
                    tag=button_tag(key),
                    width=48,
                    height=48,
                    callback=_on_click,
                    user_data=key,
                )
            else:
                # Solution de repli si le PNG est manquant : un bouton texte standard
                dpg.add_button(
                    label=title[:3], 
                    tag=button_tag(key),
                    width=-1, 
                    height=48, 
                    callback=_on_click, 
                    user_data=key
                )

            # L'infobulle reste identique
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
