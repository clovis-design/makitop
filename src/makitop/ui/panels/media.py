"""Zone « Médias » : grand panneau de gauche, dont le contenu dépend de la section choisie
dans la barre de navigation (imports, effets vidéo, effets audio, texte...)."""

import dearpygui.dearpygui as dpg

from makitop.media import thumbnails
from makitop.model.media import Media

TAG = "media_panel"
TITLE_TAG = "media_panel_title"
COLS = 3

_TEXTURE_REGISTRY = "media_texture_registry"

# (clé, titre affiché). La barre de navigation affiche un bouton par section.
SECTIONS: list[tuple[str, str]] = [
    ("imports", "Médias importés"),
    ("video_effects", "Effets vidéo"),
    ("text", "Texte"),
    ("transitions", "Transitions"),
]
DEFAULT_SECTION = SECTIONS[0][0]

_item_count = 0
_current_row_tag: str | None = None


def section_tag(key: str) -> str:
    return f"media_section_{key}"


def create() -> None:
    global _item_count, _current_row_tag
    _item_count = 0
    _current_row_tag = None
    dpg.add_texture_registry(tag=_TEXTURE_REGISTRY)
    with dpg.child_window(tag=TAG, border=True):
        dpg.add_text("", tag=TITLE_TAG)
        dpg.add_separator()
        for key, _ in SECTIONS:
            dpg.add_group(tag=section_tag(key), show=False)


def show_section(key: str) -> None:
    for other, title in SECTIONS:
        visible = other == key
        dpg.configure_item(section_tag(other), show=visible)
        if visible:
            dpg.set_value(TITLE_TAG, title)


def add_media(media: Media) -> None:
    global _item_count, _current_row_tag

    texture_tag = f"texture_{media.id}"
    dpg.add_static_texture(
        width=thumbnails.THUMB_W,
        height=thumbnails.THUMB_H,
        default_value=thumbnails.generate(media),
        tag=texture_tag,
        parent=_TEXTURE_REGISTRY,
    )

    if _item_count % COLS == 0:
        _current_row_tag = f"media_row_{_item_count // COLS}"
        dpg.add_group(
            horizontal=True,
            tag=_current_row_tag,
            parent=section_tag("imports"),
        )

    item_tag = f"media_item_{media.id}"
    dpg.add_group(tag=item_tag, parent=_current_row_tag)
    dpg.add_image(texture_tag, parent=item_tag)
    label = f"{media.name}{media.extension}"
    dpg.add_text(label[:20], parent=item_tag)

    _item_count += 1
