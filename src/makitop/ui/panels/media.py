"""Zone « Médias » : grand panneau de gauche, dont le contenu dépend de la section choisie
dans la barre de navigation (imports, effets vidéo, effets audio, texte...)."""

import threading
from collections.abc import Callable

import dearpygui.dearpygui as dpg

from makitop.media import thumbnails
from makitop.model.media import Media, MediaKind

TAG = "media_panel"
TITLE_TAG = "media_panel_title"

_TEXTURE_REGISTRY = "media_texture_registry"
_PANEL_HANDLER = "media_panel_handler"
_CLICK_HANDLER = "media_click_handler"
_ITEM_PADDING = 8
_MISSING_COLOR = (230, 90, 80)

# Icônes : constantes à remplacer par les codepoints de la police personnalisée.
_ICON_VIDEO = ">"
_ICON_AUDIO = "~"
_ICON_IMAGE = "#"

# Apparence des miniatures — modifier ici pour changer les couleurs.
_THUMB_BORDER_COLOR = (80, 80, 80, 200)  # bordure de la miniature : RGBA
_BADGE_BG_COLOR = (20, 20, 20, 210)  # fond des badges : RGBA, dernier canal = opacité (0–255)
_BADGE_TEXT_COLOR = (255, 255, 255, 255)  # texte des badges : blanc opaque
_BADGE_PAD = 3  # marge intérieure des badges en pixels
_BADGE_SIZE = 13  # taille de police des badges en pixels

# (clé, titre affiché). La barre de navigation affiche un bouton par section.
SECTIONS: list[tuple[str, str]] = [
    ("imports", "Médias importés"),
    ("bibliotheque", "Bibliothèque"),
    ("text", "Texte"),
    ("transitions", "Transitions"),
]
DEFAULT_SECTION = SECTIONS[0][0]

_medias: list[Media] = []
_current_cols: int = 0
_current_row_tag: str | None = None
_item_count: int = 0
_lock = threading.Lock()
_on_selected: Callable[[Media], None] | None = None
_on_add_media: Callable[[], None] | None = None
_active_filter: MediaKind | None = None
_filter_active_theme: int = 0
_search_query: str = ""
_sort_key: str = "import"

_ADD_BUTTON_TAG = "media_add_button"
_TITLE_ROW_TAG = "media_title_row"
_TITLE_SPACER_TAG = "media_title_spacer"
_GRID_TAG = "media_imports_grid"
_FILTER_ROW_TAG = "media_filter_row"
_SEARCH_TAG = "media_search_input"
_SORT_COMBO_TAG = "media_sort_combo"

_FILTER_OPTIONS: list[tuple[MediaKind | None, str]] = [
    (None, "Tous"),
    (MediaKind.VIDEO, "Vidéo"),
    (MediaKind.AUDIO, "Audio"),
    (MediaKind.IMAGE, "Image"),
]

_SORT_OPTIONS: list[tuple[str, str]] = [
    ("import", "Ordre d'import"),
    ("name_asc", "Nom A→Z"),
    ("name_desc", "Nom Z→A"),
    ("type", "Type"),
]
_SORT_LABEL_TO_KEY: dict[str, str] = {label: key for key, label in _SORT_OPTIONS}

_SORT_COMBO_W = 130  # largeur fixe de la liste déroulante de tri


def _filter_btn_tag(kind: MediaKind | None) -> str:
    return f"media_filter_btn_{kind.value if kind else 'all'}"


def section_tag(key: str) -> str:
    return f"media_section_{key}"


def create(
    on_selected: Callable[[Media], None] | None = None,
    on_add_media: Callable[[], None] | None = None,
) -> None:
    global _medias, _current_cols, _current_row_tag, _item_count, _on_selected, _on_add_media
    global _active_filter, _filter_active_theme, _search_query, _sort_key
    _on_selected = on_selected
    _on_add_media = on_add_media
    _medias = []
    _current_cols = 0
    _current_row_tag = None
    _item_count = 0
    _active_filter = None
    _search_query = ""
    _sort_key = "import"
    with dpg.theme() as _filter_active_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (60, 120, 175, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (80, 140, 195, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (40, 100, 155, 255))
    dpg.add_texture_registry(tag=_TEXTURE_REGISTRY)
    with dpg.item_handler_registry(tag=_PANEL_HANDLER):
        dpg.add_item_resize_handler(callback=_on_panel_resize)
    with dpg.item_handler_registry(tag=_CLICK_HANDLER):
        dpg.add_item_clicked_handler(button=dpg.mvMouseButton_Left, callback=_on_media_clicked)
    with dpg.child_window(tag=TAG, border=True):
        with dpg.group(horizontal=True, tag=_TITLE_ROW_TAG):
            dpg.add_text("", tag=TITLE_TAG)
            dpg.add_spacer(width=0, tag=_TITLE_SPACER_TAG)
            dpg.add_button(
                tag=_ADD_BUTTON_TAG,
                label="+",
                width=22,
                height=18,
                show=False,
                callback=lambda: _on_add_media() if _on_add_media else None,
            )
            with dpg.tooltip(_ADD_BUTTON_TAG):
                dpg.add_text("Ajouter des médias")
        dpg.add_separator()
        for key, _ in SECTIONS:
            with dpg.group(tag=section_tag(key), show=False):
                if key == "imports":
                    with dpg.table(
                        tag=_FILTER_ROW_TAG,
                        header_row=False,
                        borders_innerH=False,
                        borders_outerH=False,
                        borders_innerV=False,
                        borders_outerV=False,
                        width=-1,
                    ):
                        for _ in _FILTER_OPTIONS:
                            dpg.add_table_column(width_stretch=True)
                        dpg.add_table_column(
                            width_fixed=True,
                            init_width_or_weight=_SORT_COMBO_W,
                        )
                        with dpg.table_row():
                            for kind, label in _FILTER_OPTIONS:
                                with dpg.table_cell():
                                    dpg.add_button(
                                        tag=_filter_btn_tag(kind),
                                        label=label,
                                        width=-1,
                                        user_data=kind,
                                        callback=lambda s, a, u: _set_filter(u),
                                    )
                            with dpg.table_cell():
                                dpg.add_combo(
                                    tag=_SORT_COMBO_TAG,
                                    items=[label for _, label in _SORT_OPTIONS],
                                    default_value=_SORT_OPTIONS[0][1],
                                    width=-1,
                                    callback=_on_sort_change,
                                )
                    dpg.bind_item_theme(_filter_btn_tag(None), _filter_active_theme)
                    dpg.add_input_text(
                        tag=_SEARCH_TAG,
                        hint="Rechercher...",
                        width=-1,
                        callback=_on_search_change,
                    )
                    dpg.add_group(tag=_GRID_TAG)
    dpg.bind_item_handler_registry(TAG, _PANEL_HANDLER)


def _on_media_clicked(sender, app_data) -> None:
    if _on_selected is not None:
        _on_selected(dpg.get_item_user_data(app_data[1]))


def show_section(key: str) -> None:
    for other, title in SECTIONS:
        visible = other == key
        dpg.configure_item(section_tag(other), show=visible)
        if visible:
            dpg.set_value(TITLE_TAG, title)
    dpg.configure_item(_ADD_BUTTON_TAG, show=(key == "imports"))
    _update_title_spacer()


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
        if cols != _current_cols or _sort_key != "import":
            _rebuild(cols)
        elif _active_filter is None or media.kind is _active_filter:
            _append(media, cols)


def clear() -> None:
    """Retire tous les médias affichés (changement de projet)."""
    global _current_cols, _current_row_tag, _item_count, _active_filter, _search_query, _sort_key
    with _lock:
        _medias.clear()
        _current_cols = 0
        _current_row_tag = None
        _item_count = 0
        if _active_filter is not None:
            _active_filter = None
            _update_filter_themes()
        if _search_query:
            _search_query = ""
            if dpg.does_item_exist(_SEARCH_TAG):
                dpg.set_value(_SEARCH_TAG, "")
        if _sort_key != "import":
            _sort_key = "import"
            if dpg.does_item_exist(_SORT_COMBO_TAG):
                dpg.set_value(_SORT_COMBO_TAG, _SORT_OPTIONS[0][1])
        dpg.delete_item(_GRID_TAG, children_only=True)
        # Les images qui utilisaient les textures viennent d'être supprimées.
        dpg.delete_item(_TEXTURE_REGISTRY, children_only=True)


def _on_panel_resize() -> None:
    with _lock:
        _update_title_spacer()
        cols = _compute_cols()
        if cols != _current_cols and _medias:
            _rebuild(cols)


def _update_title_spacer() -> None:
    panel_size = dpg.get_item_rect_size(TAG)
    title_size = dpg.get_text_size(dpg.get_value(TITLE_TAG) or "")
    if panel_size is None or title_size is None:
        return
    spacer_w = max(0, int(panel_size[0]) - int(title_size[0]) - 22 - 30)
    dpg.configure_item(_TITLE_SPACER_TAG, width=spacer_w)


def _compute_cols() -> int:
    w = dpg.get_item_rect_size(TAG)[0]
    if w <= 0:
        return 1
    return max(1, int((w - _ITEM_PADDING) / (thumbnails.THUMB_W + _ITEM_PADDING)))


def _get_displayed_medias() -> list[Media]:
    result: list[Media] = _medias
    if _active_filter is not None:
        result = [m for m in result if m.kind is _active_filter]
    if _search_query:
        q = _search_query.lower()
        result = [m for m in result if q in m.path.stem.lower()]
    return _apply_sort(result)


def _apply_sort(medias: list[Media]) -> list[Media]:
    if _sort_key == "name_asc":
        return sorted(medias, key=lambda m: m.path.stem.lower())
    if _sort_key == "name_desc":
        return sorted(medias, key=lambda m: m.path.stem.lower(), reverse=True)
    if _sort_key == "type":
        return sorted(medias, key=lambda m: m.kind.value)
    return list(medias)


def _on_sort_change(sender, app_data) -> None:
    global _sort_key
    with _lock:
        _sort_key = _SORT_LABEL_TO_KEY.get(app_data, "import")
        cols = _compute_cols()
        _rebuild(cols)


def _on_search_change(sender, app_data) -> None:
    global _search_query
    with _lock:
        _search_query = app_data or ""
        cols = _compute_cols()
        _rebuild(cols)


def _set_filter(kind: MediaKind | None) -> None:
    global _active_filter
    with _lock:
        _active_filter = kind
        _update_filter_themes()
        cols = _compute_cols()
        _rebuild(cols)


def _update_filter_themes() -> None:
    for kind, _ in _FILTER_OPTIONS:
        tag = _filter_btn_tag(kind)
        if dpg.does_item_exist(tag):
            if kind is _active_filter:
                dpg.bind_item_theme(tag, _filter_active_theme)
            else:
                dpg.bind_item_theme(tag, 0)


def _rebuild(cols: int) -> None:
    global _current_cols, _current_row_tag, _item_count
    _current_cols = cols
    _item_count = 0
    _current_row_tag = None
    dpg.delete_item(_GRID_TAG, children_only=True)
    for m in _get_displayed_medias():
        _append(m, cols)


def _append(media: Media, cols: int) -> None:
    global _item_count, _current_row_tag
    if _item_count % cols == 0:
        _current_row_tag = f"media_row_{_item_count // cols}"
        dpg.add_group(horizontal=True, tag=_current_row_tag, parent=_GRID_TAG)

    item_tag = f"media_item_{media.id}"
    dpg.add_group(tag=item_tag, parent=_current_row_tag)

    draw_tag = f"media_draw_{media.id}"
    dpg.add_drawlist(
        tag=draw_tag,
        width=thumbnails.THUMB_W,
        height=thumbnails.THUMB_H,
        parent=item_tag,
        user_data=media,
    )
    dpg.bind_item_handler_registry(draw_tag, _CLICK_HANDLER)
    dpg.draw_image(
        f"texture_{media.id}",
        pmin=(0, 0),
        pmax=(thumbnails.THUMB_W, thumbnails.THUMB_H),
        parent=draw_tag,
    )
    _draw_overlays(draw_tag, media)

    name = _truncate(media.path.stem, thumbnails.THUMB_W)
    text_w = dpg.get_text_size(name)[0]
    indent = max(0, int((thumbnails.THUMB_W - text_w) / 2))
    name_tag = dpg.add_text(name, indent=indent, parent=item_tag, user_data=media)
    dpg.bind_item_handler_registry(name_tag, _CLICK_HANDLER)
    if not media.path.is_file():
        # Fichier déplacé ou supprimé : la fenêtre « Médias introuvables » permet de le relier.
        label = "Introuvable"
        indent = max(0, int((thumbnails.THUMB_W - dpg.get_text_size(label)[0]) / 2))
        dpg.add_text(label, parent=item_tag, indent=indent, color=_MISSING_COLOR)

    _item_count += 1


def _draw_overlays(draw_tag: str, media: Media) -> None:
    tw = thumbnails.THUMB_W
    th = thumbnails.THUMB_H

    ext = media.path.suffix.lstrip(".").upper()
    if media.kind is MediaKind.VIDEO:
        icon = _ICON_VIDEO
    elif media.kind is MediaKind.AUDIO:
        icon = _ICON_AUDIO
    else:
        icon = _ICON_IMAGE

    _draw_badge(draw_tag, ext, _BADGE_PAD, _BADGE_PAD, align="left")
    _draw_badge(draw_tag, icon, tw - _BADGE_PAD, _BADGE_PAD, align="right")

    if media.kind in (MediaKind.VIDEO, MediaKind.AUDIO) and media.duration is not None:
        dur = _format_duration(media.duration)
        _draw_badge(draw_tag, dur, tw - _BADGE_PAD, th - _BADGE_PAD - _BADGE_SIZE, align="right")

    dpg.draw_rectangle(
        (0, 0),
        (tw - 1, th - 1),
        color=_THUMB_BORDER_COLOR,
        fill=(0, 0, 0, 0),
        parent=draw_tag,
    )


def _draw_badge(draw_tag: str, text: str, x: int, y: int, align: str) -> None:
    text_w, text_h = dpg.get_text_size(text)
    if align == "right":
        x = x - int(text_w) - _BADGE_PAD * 2
    dpg.draw_rectangle(
        (x - _BADGE_PAD, y - _BADGE_PAD),
        (x + text_w + _BADGE_PAD, y + text_h + _BADGE_PAD),
        fill=_BADGE_BG_COLOR,
        color=(0, 0, 0, 0),
        parent=draw_tag,
    )
    dpg.draw_text((x, y), text, color=_BADGE_TEXT_COLOR, size=_BADGE_SIZE, parent=draw_tag)


def _format_duration(seconds: float) -> str:
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02}:{s:02}"
    return f"{m}:{s:02}"


def _truncate(name: str, max_width: float) -> str:
    if dpg.get_text_size(name)[0] <= max_width:
        return name
    ellipsis = "..."
    while name and dpg.get_text_size(name + ellipsis)[0] > max_width:
        name = name[:-1]
    return (name + ellipsis) if name else ellipsis
