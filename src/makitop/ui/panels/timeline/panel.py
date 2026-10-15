"""Panneau timeline : règle, pistes et clips."""

import dearpygui.dearpygui as dpg

from makitop.media.thumbnails import THUMB_H, THUMB_W
from makitop.model.timeline import MediaClip

TAG = "timeline_panel"
CURSOR = "timeline_cursor"
CLIPS = "timeline_clips"
IN = "timeline_source_in"
OUT = "timeline_source_out"
SELECTION = "timeline_selection"

# ── Tags ──────────────────────────────────────────────────────────────────────
_TOOLBAR_TAG = "timeline_toolbar"
_MAIN_GROUP_TAG = "timeline_main_group"
_HEADERS_TAG = "timeline_headers"
_SCROLL_TAG = "timeline_scroll"
_DRAWLIST_TAG = "timeline_drawlist"
_HANDLER_TAG = "timeline_resize_handler"
_STATIC_LAYER = "timeline_static_layer"
_PLAYHEAD_LAYER = "timeline_playhead_layer"
_CURSOR_LAYER = "timeline_cursor_layer"

# ── Dimensions ────────────────────────────────────────────────────────────────
_HEADER_W = 130     # largeur colonne labels (gauche, fixe)
_RULER_H = 24       # hauteur de la règle temporelle
_TRACK_H = 60       # hauteur d'une piste
_MIN_CONTENT_W = 800

# ── Zoom ──────────────────────────────────────────────────────────────────────
_ZOOM_LEVELS = [1, 3, 5, 8, 10, 15, 25, 35, 50, 65, 75, 100, 125, 150, 175, 200, 250, 300, 350, 400]
_DEFAULT_ZOOM_IDX = 11  # 100 px/s par défaut
_zoom_idx: int = _DEFAULT_ZOOM_IDX
_px_per_sec: int = _ZOOM_LEVELS[_DEFAULT_ZOOM_IDX]

# ── Couleurs ──────────────────────────────────────────────────────────────────
_COLOR_RULER_BG = (28, 28, 32, 255)
_COLOR_TICK = (120, 120, 130, 255)
_COLOR_TICK_LABEL = (170, 170, 180, 255)
_COLOR_CLIP_FILL = (50, 110, 170, 210)
_COLOR_CLIP_BORDER = (90, 150, 210, 255)
_COLOR_CLIP_SELECTED = (255, 200, 60, 255)
_COLOR_CLIP_TEXT = (220, 225, 235, 255)
_COLOR_PLAYHEAD = (210, 60, 60, 255)
_COLOR_CURSOR = (255, 255, 255, 55)

# ── État ──────────────────────────────────────────────────────────────────────
_clips: list[MediaClip] = []
_playhead_sec: float = 0.0
_on_seek = None       # Callable[[float], None]
_on_delete = None     # Callable[[MediaClip], None]
_on_clip_moved = None # Callable[[MediaClip], None]
_dragging: bool = False
_drag_clip: MediaClip | None = None
_drag_offset_px: float = 0.0
_selected_clip: MediaClip | None = None
_header_drag_row: int | None = None
_header_drag_target: int | None = None
_drop_indicator_theme: int = 0


def create() -> None:
    global _zoom_idx, _px_per_sec, _clips, _playhead_sec
    global _dragging, _drag_clip, _drag_offset_px, _selected_clip
    global _header_drag_row, _header_drag_target, _drop_indicator_theme
    global _on_delete, _on_clip_moved
    _zoom_idx = _DEFAULT_ZOOM_IDX
    _px_per_sec = _ZOOM_LEVELS[_DEFAULT_ZOOM_IDX]
    _clips = []
    _playhead_sec = 0.0
    _dragging = False
    _drag_clip = None
    _drag_offset_px = 0.0
    _selected_clip = None
    _header_drag_row = None
    _header_drag_target = None
    _on_delete = None
    _on_clip_moved = None

    with dpg.theme() as _drop_indicator_theme:
        with dpg.theme_component(dpg.mvChildWindow):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (255, 200, 60, 220))

    with dpg.item_handler_registry(tag=_HANDLER_TAG):
        dpg.add_item_resize_handler(callback=_on_resize)

    with dpg.child_window(tag=TAG, border=True):
        # ── Barre d'outils ────────────────────────────────────────────────────
        with dpg.group(horizontal=True, tag=_TOOLBAR_TAG):
            dpg.add_button(label="-", width=24, height=22, callback=_zoom_out)
            dpg.add_button(label="+", width=24, height=22, callback=_zoom_in)
        dpg.add_separator()

        # ── Zone principale : labels (fixe) + timeline (scrollable) ───────────
        with dpg.group(horizontal=True, tag=_MAIN_GROUP_TAG):
            with dpg.child_window(
                tag=_HEADERS_TAG,
                width=_HEADER_W,
                height=-1,
                border=False,
                no_scrollbar=True,
                no_scroll_with_mouse=True,
            ):
                dpg.add_spacer(height=_RULER_H + 2)
                dpg.add_text("Vidéo", indent=8)

            with dpg.child_window(
                tag=_SCROLL_TAG,
                width=-1,
                height=-1,
                horizontal_scrollbar=True,
                border=False,
            ):
                dpg.add_drawlist(
                    tag=_DRAWLIST_TAG,
                    width=_MIN_CONTENT_W,
                    height=_content_height(),
                )
                dpg.add_draw_layer(tag=_STATIC_LAYER, parent=_DRAWLIST_TAG)
                dpg.add_draw_layer(tag=_PLAYHEAD_LAYER, parent=_DRAWLIST_TAG)
                dpg.add_draw_layer(tag=_CURSOR_LAYER, parent=_DRAWLIST_TAG)

    dpg.bind_item_handler_registry(TAG, _HANDLER_TAG)


def add_clip(clip: MediaClip) -> None:
    _clips.append(clip)
    _redraw()


def clear() -> None:
    _clips.clear()
    _redraw()


def bind_seek(fn) -> None:
    global _on_seek
    _on_seek = fn


def bind_delete(fn) -> None:
    global _on_delete
    _on_delete = fn


def bind_clip_moved(fn) -> None:
    global _on_clip_moved
    _on_clip_moved = fn


def set_playhead(seconds: float) -> None:
    global _playhead_sec
    _playhead_sec = seconds
    _redraw_playhead()


# ── Tick (appelé chaque frame) ────────────────────────────────────────────────

def tick() -> None:
    global _dragging, _drag_clip, _drag_offset_px, _selected_clip
    btn_down = dpg.is_mouse_button_down(dpg.mvMouseButton_Left)
    _tick_header_drag(btn_down)
    if not dpg.does_item_exist(_DRAWLIST_TAG) or not dpg.does_item_exist(_CURSOR_LAYER):
        return

    hovered = dpg.is_item_hovered(_DRAWLIST_TAG)
    active = _dragging or _drag_clip is not None

    # Relâchement du bouton
    if not btn_down:
        if _drag_clip is not None:
            if _on_clip_moved is not None:
                _on_clip_moved(_drag_clip)
            _drag_clip = None
        _dragging = False

    if hovered or active:
        mx, my = dpg.get_mouse_pos(local=False)
        dl_state = dpg.get_item_state(_DRAWLIST_TAG)
        if "rect_min" not in dl_state:
            return
        dl_min = dl_state["rect_min"]
        local_x = mx - dl_min[0]
        local_y = my - dl_min[1]

        # Début d'un drag (premier frame avec bouton enfoncé, pas encore actif)
        if hovered and btn_down and not active and _header_drag_row is None:
            clip = _clip_at(local_x, local_y)
            if clip is not None:
                _drag_clip = clip
                _drag_offset_px = local_x - clip.timeline_start * _px_per_sec
                if _selected_clip is not clip:
                    _selected_clip = clip
                    _redraw_static_only()
            else:
                _selected_clip = None
                _dragging = True

        # Drag d'un clip
        if _drag_clip is not None and btn_down:
            _drag_clip.timeline_start = max(0.0, (local_x - _drag_offset_px) / _px_per_sec)
            _redraw_static_only()

        # Seek drag (pas de clip sous le curseur)
        elif _dragging and btn_down and _on_seek is not None:
            _on_seek(max(0.0, local_x / _px_per_sec))

        # Curseur hover (uniquement hors drag de clip)
        dpg.delete_item(_CURSOR_LAYER, children_only=True)
        if hovered and _drag_clip is None and local_x >= 0:
            dpg.draw_line(
                (local_x, 0), (local_x, _content_height()),
                color=_COLOR_CURSOR,
                thickness=1,
                parent=_CURSOR_LAYER,
            )
    else:
        dpg.delete_item(_CURSOR_LAYER, children_only=True)


def _tick_header_drag(btn_down: bool) -> None:
    global _header_drag_row, _header_drag_target
    exists = dpg.does_item_exist(_HEADERS_TAG)
    state = dpg.get_item_state(_HEADERS_TAG) if exists else {}
    if not exists or not _clips:
        return
    if "rect_min" not in state:
        return

    mx, my = dpg.get_mouse_pos(local=False)
    hd_min = state["rect_min"]
    local_x = mx - hd_min[0]
    local_y = my - hd_min[1]

    # Offset du premier track (spacer _RULER_H + 2 dans _HEADERS_TAG)
    track_top = _RULER_H + 2
    over_tracks = 0 <= local_x <= _HEADER_W and local_y >= track_top

    if not btn_down:
        if _header_drag_row is not None:
            saved_row, saved_target = _header_drag_row, _header_drag_target
            _header_drag_row = None
            _header_drag_target = None
            if saved_target is not None:
                _do_reorder(saved_row, saved_target)
            else:
                _update_headers()
        return

    # Début du drag : moitié supérieure de la ligne (zone titre, hors bouton ×)
    row_y_offset = (local_y - track_top) % _TRACK_H if local_y >= track_top else -1
    if over_tracks and row_y_offset < _TRACK_H // 2 and _header_drag_row is None and _drag_clip is None and not _dragging:
        row = int((local_y - track_top) / _TRACK_H)
        if 0 <= row < len(_clips):
            _header_drag_row = row
            _header_drag_target = row

    if _header_drag_row is not None:
        raw = int((local_y - track_top + _TRACK_H // 2) / _TRACK_H)
        new_target = max(0, min(len(_clips), raw))
        if new_target != _header_drag_target:
            _header_drag_target = new_target
            _update_headers()


def _do_reorder(source: int, target: int) -> None:
    insert_at = target if target <= source else target - 1
    if insert_at == source:
        return
    clip = _clips.pop(source)
    _clips.insert(insert_at, clip)
    if _on_clip_moved is not None:
        _on_clip_moved(clip)
    _redraw()


def _clip_at(local_x: float, local_y: float) -> "MediaClip | None":
    clip_h = _TRACK_H - 8
    for i, clip in enumerate(_clips):
        clip_y = _RULER_H + i * _TRACK_H + 4
        x = clip.timeline_start * _px_per_sec
        w = max(2.0, clip.duration * _px_per_sec)
        if x <= local_x <= x + w and clip_y <= local_y <= clip_y + clip_h:
            return clip
    return None


# ── Zoom ──────────────────────────────────────────────────────────────────────

def _zoom_in() -> None:
    global _zoom_idx, _px_per_sec
    if _zoom_idx < len(_ZOOM_LEVELS) - 1:
        _zoom_idx += 1
        _px_per_sec = _ZOOM_LEVELS[_zoom_idx]
        _redraw()


def _zoom_out() -> None:
    global _zoom_idx, _px_per_sec
    if _zoom_idx > 0:
        _zoom_idx -= 1
        _px_per_sec = _ZOOM_LEVELS[_zoom_idx]
        _redraw()


# ── Taille ────────────────────────────────────────────────────────────────────

def _content_height() -> int:
    return _RULER_H + max(1, len(_clips)) * _TRACK_H


def _content_width() -> int:
    scroll_w = dpg.get_item_rect_size(_SCROLL_TAG)[0] if dpg.does_item_exist(_SCROLL_TAG) else 0
    if not _clips:
        return max(_MIN_CONTENT_W, scroll_w)
    max_end = max(c.timeline_end for c in _clips)
    return max(_MIN_CONTENT_W, scroll_w, int(max_end * _px_per_sec) + 200)


def _on_resize() -> None:
    if dpg.does_item_exist(_DRAWLIST_TAG):
        dpg.configure_item(_DRAWLIST_TAG, width=_content_width(), height=_content_height())


# ── Dessin ────────────────────────────────────────────────────────────────────

def _redraw() -> None:
    if not dpg.does_item_exist(_STATIC_LAYER):
        return
    dpg.delete_item(_STATIC_LAYER, children_only=True)
    _update_headers()
    if not _clips:
        return
    w = _content_width()
    dpg.configure_item(_DRAWLIST_TAG, width=w, height=_content_height())
    _draw_ruler(w)
    _draw_clips()
    _redraw_playhead()


def _redraw_static_only() -> None:
    """Redessine règle + clips sans reconstruire les headers (utilisé pendant le drag)."""
    if not dpg.does_item_exist(_STATIC_LAYER) or not _clips:
        return
    dpg.delete_item(_STATIC_LAYER, children_only=True)
    w = _content_width()
    dpg.configure_item(_DRAWLIST_TAG, width=w, height=_content_height())
    _draw_ruler(w)
    _draw_clips()


def _redraw_playhead() -> None:
    if not dpg.does_item_exist(_PLAYHEAD_LAYER):
        return
    dpg.delete_item(_PLAYHEAD_LAYER, children_only=True)
    _draw_playhead()


def _update_headers() -> None:
    if not dpg.does_item_exist(_HEADERS_TAG):
        return
    dpg.delete_item(_HEADERS_TAG, children_only=True)
    dpg.add_spacer(height=_RULER_H + 2, parent=_HEADERS_TAG)
    for i, clip in enumerate(_clips):
        if _header_drag_target == i:
            _add_drop_indicator()
        dragging_this = _header_drag_row == i
        label_color = (150, 150, 160, 180) if dragging_this else None
        handle_color = (180, 180, 190, 180) if dragging_this else (120, 120, 130, 200)
        with dpg.child_window(
            height=_TRACK_H,
            width=-1,
            border=False,
            no_scrollbar=True,
            parent=_HEADERS_TAG,
        ):
            dpg.add_spacer(height=4)
            with dpg.group(horizontal=True):
                dpg.add_text("≡", indent=4, color=handle_color)
                label = _truncate(clip.media.path.stem, _HEADER_W - 30)
                dpg.add_text(label, color=label_color)
            dpg.add_spacer(height=2)
            dpg.add_button(
                label="×",
                width=20,
                height=20,
                indent=8,
                callback=_on_delete_btn,
                user_data=clip,
            )
    if _header_drag_target == len(_clips):
        _add_drop_indicator()


def _add_drop_indicator() -> None:
    with dpg.child_window(
        height=4,
        width=-1,
        border=False,
        no_scrollbar=True,
        parent=_HEADERS_TAG,
    ) as w:
        dpg.bind_item_theme(w, _drop_indicator_theme)


def _on_delete_btn(sender, app_data, clip: MediaClip) -> None:
    _confirm_delete(clip)


def _confirm_delete(clip: MediaClip) -> None:
    dialog_tag = "timeline_confirm_delete"
    if dpg.does_item_exist(dialog_tag):
        dpg.delete_item(dialog_tag)

    label = clip.media.path.stem
    with dpg.window(
        tag=dialog_tag,
        label="Confirmer la suppression",
        modal=True,
        no_resize=True,
        width=320,
        height=110,
        pos=(600, 300),
    ):
        dpg.add_text(f'Supprimer « {label} » de la timeline ?')
        dpg.add_spacer(height=8)
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Supprimer",
                width=100,
                callback=lambda: _do_delete(clip, dialog_tag),
            )
            dpg.add_button(
                label="Annuler",
                width=80,
                callback=lambda: dpg.delete_item(dialog_tag),
            )


def _do_delete(clip: MediaClip, dialog_tag: str) -> None:
    dpg.delete_item(dialog_tag)
    if clip in _clips:
        _clips.remove(clip)
    if _on_delete is not None:
        _on_delete(clip)
    _redraw()


def _draw_ruler(total_w: int) -> None:
    dpg.draw_rectangle(
        (0, 0), (total_w, _RULER_H),
        fill=_COLOR_RULER_BG,
        color=(0, 0, 0, 0),
        parent=_STATIC_LAYER,
    )
    # Espacement adaptatif : évite de surcharger la règle à faible zoom
    if _px_per_sec >= 50:
        minor_step, major_step = 1, 5
    elif _px_per_sec >= 10:
        minor_step, major_step = 5, 30
    else:
        minor_step, major_step = 30, 60

    max_sec = int(total_w / _px_per_sec) + 1
    s = 0
    while s <= max_sec:
        x = int(s * _px_per_sec)
        is_major = s % major_step == 0
        tick_h = 10 if is_major else 5
        dpg.draw_line(
            (x, _RULER_H - tick_h), (x, _RULER_H),
            color=_COLOR_TICK,
            parent=_STATIC_LAYER,
        )
        if is_major:
            dpg.draw_text(
                (x + 3, _RULER_H - tick_h - 13),
                _format_time(s),
                color=_COLOR_TICK_LABEL,
                size=11,
                parent=_STATIC_LAYER,
            )
        s += minor_step


def _draw_clips() -> None:
    clip_h = _TRACK_H - 8
    th_w = int(clip_h * THUMB_W / THUMB_H)

    for i, clip in enumerate(_clips):
        clip_y = _RULER_H + i * _TRACK_H + 4
        x = int(clip.timeline_start * _px_per_sec)
        w = max(2, int(clip.duration * _px_per_sec))

        border = _COLOR_CLIP_SELECTED if clip is _selected_clip else _COLOR_CLIP_BORDER
        dpg.draw_rectangle(
            (x, clip_y), (x + w, clip_y + clip_h),
            fill=_COLOR_CLIP_FILL,
            color=border,
            thickness=2 if clip is _selected_clip else 1,
            parent=_STATIC_LAYER,
        )

        texture_tag = f"texture_{clip.media.id}"
        if dpg.does_item_exist(texture_tag) and w >= 8:
            img_w = min(th_w, w)
            dpg.draw_image(
                texture_tag,
                (x, clip_y),
                (x + img_w, clip_y + clip_h),
                parent=_STATIC_LAYER,
            )

        if w >= 40:
            dpg.draw_text(
                (x + 5, clip_y + clip_h // 2 - 6),
                clip.media.path.stem,
                color=_COLOR_CLIP_TEXT,
                size=12,
                parent=_STATIC_LAYER,
            )


def _draw_playhead() -> None:
    x = int(_playhead_sec * _px_per_sec)
    total_h = _content_height()
    dpg.draw_triangle(
        (x - 6, 0), (x + 6, 0), (x, 10),
        fill=_COLOR_PLAYHEAD,
        color=(0, 0, 0, 0),
        parent=_PLAYHEAD_LAYER,
    )
    dpg.draw_line(
        (x, 0), (x, total_h),
        color=_COLOR_PLAYHEAD,
        thickness=2,
        parent=_PLAYHEAD_LAYER,
    )


def _format_time(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    if m:
        return f"{m}:{s:02}"
    return f"{s}s"


def _truncate(text: str, max_px: float) -> str:
    if dpg.get_text_size(text)[0] <= max_px:
        return text
    ellipsis = "…"
    while text and dpg.get_text_size(text + ellipsis)[0] > max_px:
        text = text[:-1]
    return (text + ellipsis) if text else ellipsis
