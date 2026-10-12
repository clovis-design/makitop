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

# --- Tailles ---
ICON_SIZE = 36          # la valeur pour agrandir/réduire l'icône
SIDEBAR_WIDTH = 80      # Largeur estimée de la barre (pour le calcul du centrage)

# Textes courts à afficher sous les icônes
SUBTITLES: dict[str, str] = {
    "imports": "Médias",
    "bibliotheque": "Bibliothèque",
    "text": "Texte",
    "transitions": "Transitions",
}


def button_tag(key: str) -> str:
    return f"sidebar_button_{key}"


def texture_tag(key: str) -> str:
    return f"sidebar_texture_{key}"


def load_icon_textures() -> None:
    if not dpg.does_alias_exist("sidebar_texture_registry"):
        with dpg.texture_registry(tag="sidebar_texture_registry"):
            for key, filename in ICON_FILES.items():
                filepath = ICONS_DIR / filename
                if filepath.exists():
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
    load_icon_textures()

    # 1. Thème de base de la sidebar (Boutons transparents par défaut)
    with dpg.theme(tag="sidebar_base_theme"):
        with dpg.theme_component(dpg.mvImageButton):
            # (Rouge, Vert, Bleu, Alpha=0 pour la transparence)
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))

    # 2. Thème pour le bouton actif (Bleu)
    with dpg.theme(tag=SELECTED_THEME):
        with dpg.theme_component(dpg.mvImageButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (41, 74, 122))
            # Plus la valeur est haute, plus c'est arrondi (ex: 8 à 12 pour des coins doux)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 20)
            
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (41, 74, 122))
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 20)
    # 3. Thème pour l'infobulle (texte au survol / hover)
    with dpg.theme(tag="sidebar_tooltip_theme"):
        with dpg.theme_component(dpg.mvTooltip):
            dpg.add_theme_color(dpg.mvThemeCol_PopupBg, (11, 17, 41, 230))
            dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 8, 6)

    # 4. Thème pour adoucir la couleur des sous-titres (gris clair)
    with dpg.theme(tag="sidebar_subtitle_theme"):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (180, 180, 185, 255))

    with dpg.child_window(tag=TAG, border=False, no_scrollbar=True):
        # On applique le thème de base avec fond transparent à toute la sidebar
        dpg.bind_item_theme(TAG, "sidebar_base_theme")
        
        dpg.add_spacer(height=15)
        
        for key, title in media.SECTIONS:
            tex_tag = texture_tag(key)
            
            # --- CALCUL DU CENTRAGE DE L'ICÔNE ---
            icon_indent = (SIDEBAR_WIDTH - ICON_SIZE) // 2
            
            if dpg.does_alias_exist(tex_tag):
                dpg.add_image_button(
                    texture_tag=tex_tag,
                    tag=button_tag(key),
                    width=ICON_SIZE,
                    height=ICON_SIZE,
                    callback=_on_click,
                    user_data=key,
                    indent=icon_indent
                )
            else:
                dpg.add_button(
                    label=title[:3], 
                    tag=button_tag(key),
                    width=ICON_SIZE, 
                    height=ICON_SIZE, 
                    callback=_on_click, 
                    user_data=key,
                    indent=icon_indent
                )

            # --- INFOBULLE AU SURVOL (Hover) ---
            with dpg.tooltip(button_tag(key)) as tt:
                dpg.add_text(title)
                dpg.bind_item_theme(tt, "sidebar_tooltip_theme")

            # --- SOUS-TITRE FIXE EN DESSOUS ---
            subtitle_text = SUBTITLES.get(key, title)
            
            # Limite le texte à 6 caractères, ajoute un point si c'est plus long
            max_chars = 6
            if len(subtitle_text) > max_chars:
                subtitle_text = subtitle_text[:max_chars] + "."

            # Ajustement du retrait basé sur le texte final
            text_indent = max(0, icon_indent + (ICON_SIZE // 2) - (len(subtitle_text) * 3))
            
            txt_id = dpg.add_text(subtitle_text, indent=text_indent)
            
            # Application de la couleur (Gris) ET de la police (Taille 8)
            dpg.bind_item_theme(txt_id, "sidebar_subtitle_theme")
            if dpg.does_alias_exist("small_text_font"):
                dpg.bind_item_font(txt_id, "small_text_font")
                
            dpg.add_spacer(height=15)


def select(key: str) -> None:
    _highlight(key)
    media.show_section(key)


def _highlight(key: str) -> None:
    for other, _ in media.SECTIONS:
        dpg.bind_item_theme(button_tag(other), SELECTED_THEME if other == key else 0)


def _on_click(sender, app_data, user_data: str) -> None:
    select(user_data)