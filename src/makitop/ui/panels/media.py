"""Zone « Médias » : grand panneau de gauche, dont le contenu dépend de la section choisie
dans la barre de navigation (imports, effets vidéo, effets audio, texte...)."""

import threading

import dearpygui.dearpygui as dpg

from makitop.media import thumbnails
from makitop.model.media import Media

TAG = "media_panel"
TITLE_TAG = "media_panel_title"

_TEXTURE_REGISTRY = "media_texture_registry"
_PANEL_HANDLER = "media_panel_handler"
_ITEM_PADDING = 8

# (clé, titre affiché). La barre de navigation affiche un bouton par section.
SECTIONS: list[tuple[str, str]] = [
    ("imports", "Médias importés"),
    ("video_effects", "Effets vidéo"),
    ("text", "Texte"),
    ("transitions", "Transitions"),
]
DEFAULT_SECTION = SECTIONS[0][0]

_medias: list[Media] = []
_current_cols: int = 0
_current_row_tag: str | None = None
_item_count: int = 0
_lock = threading.Lock()


def section_tag(key: str) -> str:
    return f"media_section_{key}"


def create() -> None:
    global _medias, _current_cols, _current_row_tag, _item_count
    _medias = []
    _current_cols = 0
    _current_row_tag = None
    _item_count = 0
    dpg.add_texture_registry(tag=_TEXTURE_REGISTRY)
    with dpg.item_handler_registry(tag=_PANEL_HANDLER):
        dpg.add_item_resize_handler(callback=_on_panel_resize)
    with dpg.child_window(tag=TAG, border=True):
        dpg.add_text("", tag=TITLE_TAG)
        dpg.add_separator()
        for key, _ in SECTIONS:
            dpg.add_group(tag=section_tag(key), show=False)
    dpg.bind_item_handler_registry(TAG, _PANEL_HANDLER)


def show_section(key: str) -> None:
    for other, title in SECTIONS:
        visible = other == key
        dpg.configure_item(section_tag(other), show=visible)
        if visible:
            dpg.set_value(TITLE_TAG, title)


def add_media(media: Media) -> None:
    with _lock:
        _medias.append(media)
        dpg.add_static_texture(
            width=thumbnails.THUMB_W,
            height=thumbnails.THUMB_H,
            default_value=thumbnails.generate(media),
            tag=f"texture_{media.id}",
            parent=_TEXTURE_REGISTRY,
        )
        cols = _compute_cols()
        if cols != _current_cols:
            _rebuild(cols)
        else:
            _append(media, cols)


def _on_panel_resize() -> None:
    with _lock:
        cols = _compute_cols()
        if cols != _current_cols and _medias:
            _rebuild(cols)


def _compute_cols() -> int:
    w = dpg.get_item_rect_size(TAG)[0]
    if w <= 0:
        return 1
    return max(1, int((w - _ITEM_PADDING) / (thumbnails.THUMB_W + _ITEM_PADDING)))


def _rebuild(cols: int) -> None:
    global _current_cols, _current_row_tag, _item_count
    _current_cols = cols
    _item_count = 0
    _current_row_tag = None
    dpg.delete_item(section_tag("imports"), children_only=True)
    for m in _medias:
        _append(m, cols)


def _append(media: Media, cols: int) -> None:
    global _item_count, _current_row_tag
    if _item_count % cols == 0:
        _current_row_tag = f"media_row_{_item_count // cols}"
        dpg.add_group(horizontal=True, tag=_current_row_tag, parent=section_tag("imports"))

    item_tag = f"media_item_{media.id}"
    dpg.add_group(tag=item_tag, parent=_current_row_tag)
    dpg.add_image(f"texture_{media.id}", parent=item_tag)

    name = _truncate(media.name, thumbnails.THUMB_W)
    text_w = dpg.get_text_size(name)[0]
    indent = max(0, int((thumbnails.THUMB_W - text_w) / 2))
    text_row_tag = f"media_text_{media.id}"
    dpg.add_group(horizontal=True, tag=text_row_tag, parent=item_tag)
    if indent > 0:
        dpg.add_spacer(width=indent, parent=text_row_tag)
    dpg.add_text(name, parent=text_row_tag)

    _item_count += 1


def _truncate(name: str, max_width: float) -> str:
    if dpg.get_text_size(name)[0] <= max_width:
        return name
    ellipsis = "..."
    while name and dpg.get_text_size(name + ellipsis)[0] > max_width:
        name = name[:-1]
    return (name + ellipsis) if name else ellipsis
