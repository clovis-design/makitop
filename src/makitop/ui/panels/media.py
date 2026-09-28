"""Zone « Médias » : grand panneau de gauche, dont le contenu dépend de la section choisie
dans la barre de navigation (imports, effets vidéo, effets audio, texte...)."""

import dearpygui.dearpygui as dpg
import os
from makitop.ui.assets.style import COLORS, FONT_INTER 

TAG = "media_panel"
TITLE_TAG = "media_panel_title"

# (clé, titre affiché). La barre de navigation affiche un bouton par section.
SECTIONS: list[tuple[str, str]] = [
    ("imports", "Médias importés"),
    ("video_effects", "Effets vidéo"),
    ("audio_effects", "Effets audio"),
    ("text", "Texte"),
    ("transitions", "Transitions"),
]
DEFAULT_SECTION = SECTIONS[0][0]


def section_tag(key: str) -> str:
    return f"media_section_{key}"


def create() -> None:
    with dpg.child_window(tag=TAG, border=False):
        dpg.add_text("", tag=TITLE_TAG)
        dpg.add_separator()
        for key, _ in SECTIONS:
            # Chaque section est un groupe vide, à remplir avec la feature correspondante.
            dpg.add_group(tag=section_tag(key), show=False)
    apply_media_style()


def show_section(key: str) -> None:
    for other, title in SECTIONS:
        visible = other == key
        dpg.configure_item(section_tag(other), show=visible)
        if visible:
            dpg.set_value(TITLE_TAG, title)

def apply_media_style() -> None:
    """Applique la couleur de fond et la police au panneau des médias."""
    
    # 1. Changement de la couleur de fond
    with dpg.theme() as media_theme:
        # On cible explicitement les fenêtres enfants (child_window)
        with dpg.theme_component(dpg.mvChildWindow):
            # Couleur de fond : un gris bleuté sombre par exemple (R, V, B, Alpha)
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_main"])
            
        # On cible les textes à l'intérieur du panneau
        with dpg.theme_component(dpg.mvAll):
            # Couleur du texte : un blanc cassé pour ne pas agresser l'œil
            dpg.add_theme_color(dpg.mvThemeCol_Text, (220, 220, 225, 255))

    # On lie le thème au panneau
    dpg.bind_item_theme(TAG, media_theme)

    # 2. Changement de la police (Nécessite un fichier .ttf sur ton disque)
    # Chemin vers ta police (à adapter selon ton dossier de projet)
    font_path = "src/makitop/ui/assets/fonts/Inter-VariableFont_slnt,wght.ttf" 
    
    # DearPyGui requiert un registre de polices
    if os.path.exists(font_path):
        # On vérifie si un registre de police existe déjà pour ne pas le recréer
        if not dpg.does_alias_exist("font_registry"):
            dpg.add_font_registry(tag="font_registry")
            
        with dpg.font_registry():
            # Charge la police avec une taille de 16 pixels
            media_font = dpg.add_font(font_path, 16)
            
        # On lie la police au panneau des médias et à tous ses enfants
        dpg.bind_item_font(TAG, media_font)
    else:
        print(f"Attention : Le fichier de police {font_path} est introuvable.")
