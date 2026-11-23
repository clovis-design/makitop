"""Zone « Médias » : grand panneau de gauche, dont le contenu dépend de la section choisie
dans la barre de navigation (imports, effets vidéo, effets audio, texte...)."""

import threading
from collections.abc import Callable

import dearpygui.dearpygui as dpg

from makitop.media import thumbnails
from makitop.model.media import Media, MediaKind
from makitop.ui.panels import effects as effects_panel
from makitop.ui.panels import text_presets

TAG = "media_panel"
TITLE_TAG = "media_panel_title"
CONTENT_TAG = "media_content_container"

_TEXTURE_REGISTRY = "media_texture_registry"
_PANEL_HANDLER = "media_panel_handler"
_CLICK_HANDLER = "media_click_handler"
_ITEM_PADDING = 8
_MISSING_COLOR = (230, 90, 80)

_ICON_VIDEO = ">"
_ICON_AUDIO = "~"
_ICON_IMAGE = "#"

_THUMB_BORDER_COLOR = (80, 80, 80, 200)
_BADGE_BG_COLOR = (20, 20, 20, 210)
_BADGE_TEXT_COLOR = (255, 255, 255, 255)
_BADGE_PAD = 3
_BADGE_SIZE = 13

SECTIONS: list[tuple[str, str]] = [
    ("imports", "Médias importés"),
    ("bibliotheque", "Bibliothèque"),
    ("effects", "Effets"),
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
_on_add_to_timeline: Callable[[Media], None] | None = None
_on_delete_media: Callable[[Media], None] | None = None
_right_clicked_media: Media | None = None
_active_filter: MediaKind | None = None
_filter_active_theme: int = 0
_search_query: str = ""
_sort_key: str = "import"

# Drag & drop vers la timeline
_hovered_media: Media | None = None
_hover_set_this_tick: bool = False
_drag_candidate: Media | None = None
_drag_start_pos: tuple | None = None
_dragging_media: Media | None = None
_drag_active: bool = False
_prev_btn_down: bool = False
_ghost_drawn_for: "Media | None" = None

_DRAG_GHOST_TAG = "media_drag_ghost_window"
_DRAG_GHOST_DL = "media_drag_ghost_drawlist"

_ADD_BUTTON_TAG = "media_add_button"
_CTX_ADD_TO_TIMELINE_TAG = "media_ctx_add_to_timeline"
_CTX_DELETE_TAG = "media_ctx_delete"
_TITLE_ROW_TAG = "media_title_row"
_TITLE_SPACER_TAG = "media_title_spacer"
_GRID_TAG = "media_imports_grid"
_FILTER_ROW_TAG = "media_filter_row"
_SEARCH_TAG = "media_search_input"
_SORT_COMBO_TAG = "media_sort_combo"
_CONTEXT_MENU_TAG = "media_context_menu"

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
_SORT_COMBO_W = 130


def _filter_btn_tag(kind: MediaKind | None) -> str:
    return f"media_filter_btn_{kind.value if kind else 'all'}"


def section_tag(key: str) -> str:
    return f"media_section_{key}"


def create(
    on_selected: Callable[[Media], None] | None = None,
    on_add_media: Callable[[], None] | None = None,
    on_add_to_timeline: Callable[[Media], None] | None = None,
    on_add_text: Callable[[str], None] | None = None,
) -> None:
    global _medias, _current_cols, _current_row_tag, _item_count, _on_selected, _on_add_media
    global _active_filter, _filter_active_theme, _search_query, _sort_key, _on_add_to_timeline, _on_delete_media
    global _hovered_media, _hover_set_this_tick, _drag_candidate, _drag_start_pos
    global _dragging_media, _drag_active, _prev_btn_down
    _on_selected = on_selected
    _on_add_media = on_add_media
    _on_add_to_timeline = on_add_to_timeline
    _on_delete_media = None
    _medias = []
    _current_cols = 0
    _current_row_tag = None
    _item_count = 0
    _active_filter = None
    _search_query = ""
    _sort_key = "import"
    _hovered_media = None
    _hover_set_this_tick = False
    _drag_candidate = None
    _drag_start_pos = None
    _dragging_media = None
    _drag_active = False
    _prev_btn_down = False
    _ghost_drawn_for = None

    # 1. THÈME DU PANNEAU
    with dpg.theme(tag="media_panel_theme"):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 12, 12)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 6)

    # 2. THÈME DU BOUTON FILTRE ACTIF
    with dpg.theme() as _filter_active_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (60, 120, 175, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (80, 140, 195, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (40, 100, 155, 255))
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8)

    # Fenêtre flottante ghost pour drag & drop (créée au niveau viewport)
    with dpg.window(
        tag=_DRAG_GHOST_TAG,
        no_title_bar=True,
        no_resize=True,
        no_move=True,
        no_scrollbar=True,
        no_collapse=True,
        no_saved_settings=True,
        no_focus_on_appearing=True,
        no_background=True,
        autosize=True,
        show=False,
        min_size=[1, 1],
    ):
        dpg.add_drawlist(
            tag=_DRAG_GHOST_DL,
            width=thumbnails.THUMB_W,
            height=thumbnails.THUMB_H + 18,
        )

    dpg.add_texture_registry(tag=_TEXTURE_REGISTRY)
    
    with dpg.item_handler_registry(tag=_PANEL_HANDLER):
        dpg.add_item_resize_handler(callback=_on_panel_resize)
        
    with dpg.item_handler_registry(tag=_CLICK_HANDLER):
        dpg.add_item_clicked_handler(button=dpg.mvMouseButton_Left, callback=_on_media_clicked)
        dpg.add_item_clicked_handler(button=dpg.mvMouseButton_Right, callback=_on_media_right_clicked)
        dpg.add_item_hover_handler(callback=_on_media_hover)
        dpg.add_item_clicked_handler(button=dpg.mvMouseButton_Left, callback=_on_media_press)
    with dpg.window(
        tag=_CONTEXT_MENU_TAG,
        popup=True,
        show=False,
        no_title_bar=True,
        no_move=True,
        no_resize=True,
        autosize=True,
        min_size=[1, 1],
    ):
        dpg.add_menu_item(
            tag=_CTX_ADD_TO_TIMELINE_TAG,
            label="Ajouter à la timeline",
            callback=_on_context_add_to_timeline,
        )
        dpg.add_separator()
        dpg.add_menu_item(
            tag=_CTX_DELETE_TAG,
            label="Supprimer",
            callback=_on_context_delete,
        )
    with dpg.child_window(tag=TAG, border=False):
        dpg.bind_item_theme(TAG, "media_panel_theme")

        dpg.add_spacer(height=4)

        with dpg.group(horizontal=True, tag=_TITLE_ROW_TAG, indent=16):
            dpg.add_text("", tag=TITLE_TAG)
            dpg.add_spacer(width=0, tag=_TITLE_SPACER_TAG)
            dpg.add_button(
                tag=_ADD_BUTTON_TAG,
                label="+",
                width=24,
                height=24,
                show=False,
                callback=lambda: _on_add_media() if _on_add_media else None,
            )
            with dpg.tooltip(_ADD_BUTTON_TAG):
                dpg.add_text("Ajouter des médias")
        # Le séparateur ignore l'indentation, ce qui donne un bel effet "bord à bord" moderne
        dpg.add_separator(indent=16)
        
        # Groupe principal du contenu : tout est poussé de 16px vers la droite
        with dpg.group(tag="media_padded_content", indent=16):
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
                            width=100, # Largeur temporaire, écrasée instantanément par _on_panel_resize
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
                            width=100, # Largeur temporaire
                            callback=_on_search_change,
                        )
                        
                        dpg.add_spacer(height=8)
                        dpg.add_group(tag=_GRID_TAG)
                    elif key == "effects":
                        effects_panel.build()
                    elif key == "text":
                        text_presets.build(on_add_text)

    dpg.bind_item_handler_registry(TAG, _PANEL_HANDLER)


def _on_panel_resize() -> None:
    with _lock:
        w = dpg.get_item_rect_size(TAG)[0]
        # On calcule mathématiquement la marge de droite
        if w > 32:
            inner_w = w - 32 # Largeur totale moins 16px à gauche et 16px à droite
            
            # On force les barres étirables à adopter cette largeur parfaite
            if dpg.does_item_exist(_FILTER_ROW_TAG):
                dpg.configure_item(_FILTER_ROW_TAG, width=inner_w)
            if dpg.does_item_exist(_SEARCH_TAG):
                dpg.configure_item(_SEARCH_TAG, width=inner_w)
                
        _update_title_spacer()
        cols = _compute_cols()
        if cols != _current_cols and _medias:
            _rebuild(cols)


def _compute_cols() -> int:
    w = dpg.get_item_rect_size(TAG)[0]
    if w <= 32:
        return 1
    # On précise à l'algorithme des miniatures que la largeur utile est amputée de 32px
    w_inner = w - 32
    return max(1, int((w_inner - _ITEM_PADDING) / (thumbnails.THUMB_W + _ITEM_PADDING)))


def _update_title_spacer() -> None:
    # 1. Vérification de sécurité au cas où l'élément n'existe pas encore
    if not dpg.does_item_exist(TAG) or not dpg.does_item_exist(TITLE_TAG):
        return

    # 2. On récupère la taille du panneau principal (TAG)
    panel_size = dpg.get_item_rect_size(TAG)
    title_size = dpg.get_text_size(dpg.get_value(TITLE_TAG) or "")

    # 3. Protection critique : Au lancement de l'application, la taille est [0, 0]
    # car la carte graphique n'a pas encore dessiné la fenêtre. On ignore le calcul.
    if not panel_size or not title_size or panel_size[0] <= 0:
        return

    # 4. Calcul de l'espacement :
    # On retire 32px (16px de padding à gauche + 16px à droite)
    # On retire 60px pour la largeur du bouton "+" et une marge de sécurité
    spacer_w = max(0, int(panel_size[0]) - int(title_size[0]) - 32 - 60)
    
    if dpg.does_item_exist(_TITLE_SPACER_TAG):
        dpg.configure_item(_TITLE_SPACER_TAG, width=spacer_w)


def _on_media_clicked(sender, app_data) -> None:
    if _on_selected is not None:
        _on_selected(dpg.get_item_user_data(app_data[1]))


def _on_media_right_clicked(sender, app_data) -> None:
    global _right_clicked_media
    media = dpg.get_item_user_data(app_data[1])
    if not isinstance(media, Media):
        return
    _right_clicked_media = media
    is_video = media.kind is MediaKind.VIDEO
    if dpg.does_item_exist(_CTX_ADD_TO_TIMELINE_TAG):
        dpg.configure_item(_CTX_ADD_TO_TIMELINE_TAG, show=is_video)
    dpg.configure_item(_CONTEXT_MENU_TAG, show=True, pos=list(dpg.get_mouse_pos()))


def _on_context_add_to_timeline() -> None:
    if _right_clicked_media is not None and _on_add_to_timeline is not None:
        _on_add_to_timeline(_right_clicked_media)


def _on_context_delete() -> None:
    if _right_clicked_media is None:
        return
    _confirm_delete_media(_right_clicked_media)


def _confirm_delete_media(media: Media) -> None:
    dialog_tag = "media_confirm_delete"
    if dpg.does_item_exist(dialog_tag):
        dpg.delete_item(dialog_tag)

    label = media.path.stem
    w, h = 360, 120
    vw, vh = dpg.get_viewport_width(), dpg.get_viewport_height()
    with dpg.window(
        tag=dialog_tag,
        label="Confirmer la suppression",
        modal=True,
        no_resize=True,
        width=w,
        height=h,
        pos=((vw - w) // 2, (vh - h) // 2),
    ):
        dpg.add_text(f'Supprimer « {label} » et tous ses clips de la timeline ?')
        dpg.add_spacer(height=8)
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Supprimer",
                width=100,
                callback=lambda: _do_delete_media(media, dialog_tag),
            )
            dpg.add_button(
                label="Annuler",
                width=80,
                callback=lambda: dpg.delete_item(dialog_tag),
            )


def _do_delete_media(media: Media, dialog_tag: str) -> None:
    dpg.delete_item(dialog_tag)
    if _on_delete_media is not None:
        _on_delete_media(media)


def _on_media_hover(sender, app_data) -> None:
    global _hovered_media, _hover_set_this_tick
    media = dpg.get_item_user_data(app_data)
    if isinstance(media, Media):
        _hovered_media = media
        _hover_set_this_tick = True


def _on_media_press(sender, app_data) -> None:
    """Capte le mouse-down directement sur l'item — plus fiable que l'état hover."""
    global _drag_candidate, _drag_start_pos
    media = dpg.get_item_user_data(app_data[1])
    if isinstance(media, Media):
        _drag_candidate = media
        _drag_start_pos = dpg.get_mouse_pos(local=False)


def get_dragging_media() -> "Media | None":
    return _dragging_media if _drag_active else None


def tick() -> None:
    global _hovered_media, _hover_set_this_tick, _drag_candidate, _drag_start_pos
    global _dragging_media, _drag_active, _prev_btn_down, _ghost_drawn_for

    # Nettoyage du hover si aucun handler n'a signalé de survol ce tick
    if not _hover_set_this_tick:
        _hovered_media = None
    _hover_set_this_tick = False

    btn = dpg.is_mouse_button_down(dpg.mvMouseButton_Left)

    # Seuil de mouvement → drag actif
    if btn and _drag_candidate is not None and not _drag_active and _drag_start_pos is not None:
        pos = dpg.get_mouse_pos(local=False)
        if abs(pos[0] - _drag_start_pos[0]) > 5 or abs(pos[1] - _drag_start_pos[1]) > 5:
            _drag_active = True
            _dragging_media = _drag_candidate

    # Fenêtre ghost qui suit le curseur
    if _drag_active and _dragging_media is not None and dpg.does_item_exist(_DRAG_GHOST_TAG):
        pos = dpg.get_mouse_pos(local=False)
        dpg.configure_item(_DRAG_GHOST_TAG, pos=(int(pos[0]) + 16, int(pos[1]) + 16), show=True)
        if _ghost_drawn_for is not _dragging_media:
            _ghost_drawn_for = _dragging_media
            _redraw_ghost(_dragging_media)
            dpg.focus_item(_DRAG_GHOST_TAG)  # forcer au premier plan à chaque nouveau drag
    elif dpg.does_item_exist(_DRAG_GHOST_TAG):
        # Pousser hors de l'écran (coordonnées positives pour éviter le clamping DPG)
        vw = dpg.get_viewport_width()
        dpg.configure_item(_DRAG_GHOST_TAG, show=False, pos=[vw + 200, 0])

    # Relâchement
    if not btn:
        _drag_candidate = None
        _drag_start_pos = None
        _drag_active = False
        _dragging_media = None
        _ghost_drawn_for = None

    _prev_btn_down = btn


def _redraw_ghost(media: Media) -> None:
    if not dpg.does_item_exist(_DRAG_GHOST_DL):
        return
    dpg.delete_item(_DRAG_GHOST_DL, children_only=True)
    tw, th = thumbnails.THUMB_W, thumbnails.THUMB_H
    texture_tag = f"texture_{media.id}"
    if dpg.does_item_exist(texture_tag):
        dpg.draw_image(texture_tag, (0, 0), (tw, th), parent=_DRAG_GHOST_DL)
    # Voile semi-transparent pour l'effet ghost
    dpg.draw_rectangle(
        (0, 0), (tw, th),
        fill=(0, 0, 0, 90),
        color=(100, 200, 120, 180),
        thickness=2,
        parent=_DRAG_GHOST_DL,
    )
    # Nom du média en dessous
    name = _truncate(media.path.stem, tw)
    dpg.draw_text(
        (2, th + 2), name,
        color=(220, 225, 235, 230),
        size=12,
        parent=_DRAG_GHOST_DL,
    )


def bind_delete_media(fn: Callable[[Media], None]) -> None:
    global _on_delete_media
    _on_delete_media = fn


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
