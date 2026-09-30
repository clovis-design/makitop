"""Zone « Médias » : grand panneau de gauche, dont le contenu dépend de la section choisie
dans la barre de navigation (imports, effets vidéo, effets audio, texte...)."""

import dearpygui.dearpygui as dpg

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


def show_section(key: str) -> None:
    for other, title in SECTIONS:
        visible = other == key
        dpg.configure_item(section_tag(other), show=visible)
        if visible:
            dpg.set_value(TITLE_TAG, title)
