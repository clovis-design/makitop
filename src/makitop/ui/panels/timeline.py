"""Zone « Timeline » : pistes et clips (Dear PyGui Plot)."""

import dearpygui.dearpygui as dpg
import os
from makitop.ui.assets.style import COLORS, FONT_INTER

TAG = "timeline_panel"


def create() -> None:
    with dpg.child_window(tag=TAG, border=True):
        dpg.add_text("Timeline")
        dpg.add_separator()
    apply_media_style()

def apply_media_style() -> None:
    """Applique la couleur de fond et la police au panneau des médias."""
    
    # 1. Changement de la couleur de fond
    with dpg.theme() as timeline_theme:
        # On cible explicitement les fenêtres enfants (child_window)
        with dpg.theme_component(dpg.mvChildWindow):
            # Couleur de fond : un gris bleuté sombre par exemple (R, V, B, Alpha)
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_main"])
            
        # On cible les textes à l'intérieur du panneau
        with dpg.theme_component(dpg.mvAll):
            # Couleur du texte : un blanc cassé pour ne pas agresser l'œil
            dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text_main"])

    # On lie le thème au panneau
    dpg.bind_item_theme(TAG, timeline_theme)

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
            timeline_font = dpg.add_font(font_path, 16)
            
        # On lie la police au panneau des médias et à tous ses enfants
        dpg.bind_item_font(TAG, timeline_font)
    else:
        print(f"Attention : Le fichier de police {font_path} est introuvable.")
