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
_ZOOM_LEVELS = [1, 2, 3, 4, 5, 6, 8, 10, 13, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 155, 195, 245, 310, 390]
_DEFAULT_ZOOM_IDX = 17  # 100 px/s par défaut
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
_COLOR_FX_BADGE = (140, 90, 220, 230)
_COLOR_PLAYHEAD = (210, 60, 60, 255)
_COLOR_CURSOR = (255, 255, 255, 55)

# ── État ──────────────────────────────────────────────────────────────────────
# _tracks[0] = piste en haut (priorité la plus haute dans le lecteur)
_tracks: list[list[MediaClip]] = []
_playhead_sec: float = 0.0
_on_seek = None            # Callable[[float], None]
_on_delete = None          # Callable[[MediaClip], None]
_on_clip_moved = None      # Callable[[MediaClip], None]  — drag d'un clip
_on_track_reordered = None # Callable[[], None]           — réordonnancement ▲/▼
_on_select = None          # Callable[[MediaClip], None]
_on_zoom = None            # Callable[[int], None]        — nouveau zoom en px/s
_dragging: bool = False
_drag_clip: MediaClip | None = None
_drag_offset_px: float = 0.0
_selected_clip: MediaClip | None = None
_pending_fit_zoom: bool = False


def create() -> None:
    global _zoom_idx, _px_per_sec, _tracks, _playhead_sec
    global _dragging, _drag_clip, _drag_offset_px, _selected_clip
    global _on_delete, _on_clip_moved, _on_track_reordered, _on_select, _on_zoom, _pending_fit_zoom
    _zoom_idx = _DEFAULT_ZOOM_IDX
    _px_per_sec = _ZOOM_LEVELS[_DEFAULT_ZOOM_IDX]
    _tracks = []
    _playhead_sec = 0.0
    _dragging = False
    _drag_clip = None
    _drag_offset_px = 0.0
    _selected_clip = None
    _on_delete = None
    _on_clip_moved = None
    _on_track_reordered = None
    _on_select = None
    _on_zoom = None
    _pending_fit_zoom = False

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
    """Ajoute un clip dans la piste correspondante (créée si inexistante)."""
    for row in _tracks:
        if row and row[0].track == clip.track:
            row.append(clip)
            row.sort(key=lambda c: c.timeline_start)
            _redraw()
            return
    # Nouvelle piste : insérer en respectant l'ordre décroissant de track
    new_row = [clip]
    for i, row in enumerate(_tracks):
        if row and row[0].track < clip.track:
            _tracks.insert(i, new_row)
            _redraw()
            return
    _tracks.append(new_row)
    _redraw()


def clear() -> None:
    _tracks.clear()
    _redraw()


def fit_zoom() -> None:
    global _pending_fit_zoom
    _pending_fit_zoom = True


def _apply_fit_zoom() -> None:
    global _zoom_idx, _px_per_sec, _pending_fit_zoom
    all_clips = _all_clips()
    if not all_clips:
        return  # Pas encore de clips — retenter au prochain tick
    total_duration = max(c.timeline_end for c in all_clips)
    if total_duration <= 0:
        return
    available_w = 0
    if dpg.does_item_exist(_SCROLL_TAG):
        available_w = dpg.get_item_rect_size(_SCROLL_TAG)[0]
    if available_w <= 32 and dpg.does_item_exist(TAG):
        available_w = max(0, dpg.get_item_rect_size(TAG)[0] - _HEADER_W - 20)
    if available_w <= 32:
        return  # UI pas encore rendue — on retente au prochain frame
    _pending_fit_zoom = False
    ideal = available_w / total_duration
    best = max((i for i, v in enumerate(_ZOOM_LEVELS) if v <= ideal), default=0)
    _zoom_idx = best
    _px_per_sec = _ZOOM_LEVELS[_zoom_idx]
    _redraw()


def get_clip_ids() -> list[str]:
    """Retourne tous les IDs de clips, piste par piste (haut → bas), chronologiques."""
    return [c.id for row in _tracks for c in row]


def get_track_rows() -> list[list[str]]:
    """Retourne les IDs de clips groupés par piste (haut → bas)."""
    return [[c.id for c in row] for row in _tracks]


def bind_seek(fn) -> None:
    global _on_seek
    _on_seek = fn


def bind_delete(fn) -> None:
    global _on_delete
    _on_delete = fn


def bind_clip_moved(fn) -> None:
    global _on_clip_moved
    _on_clip_moved = fn


def bind_track_reordered(fn) -> None:
    global _on_track_reordered
    _on_track_reordered = fn


def bind_select(fn) -> None:
    global _on_select
    _on_select = fn


def bind_zoom(fn) -> None:
    global _on_zoom
    _on_zoom = fn


def set_zoom(pixels_per_second: int) -> None:
    """Applique un zoom enregistré (niveau le plus proche), sans notifier l'éditeur."""
    global _zoom_idx, _px_per_sec
    _zoom_idx = min(range(len(_ZOOM_LEVELS)), key=lambda i: abs(_ZOOM_LEVELS[i] - pixels_per_second))
    _px_per_sec = _ZOOM_LEVELS[_zoom_idx]
    _redraw()


def set_selected(clip_id: str | None) -> None:
    global _selected_clip
    _selected_clip = next((c for c in _all_clips() if c.id == clip_id), None) if clip_id else None
    _redraw_static_only()


def set_playhead(seconds: float) -> None:
    global _playhead_sec
    _playhead_sec = seconds
    _redraw_playhead()


# ── Tick (appelé chaque frame) ────────────────────────────────────────────────

def tick() -> None:
    global _dragging, _drag_clip, _drag_offset_px, _selected_clip
    if _pending_fit_zoom:
        _apply_fit_zoom()
    btn_down = dpg.is_mouse_button_down(dpg.mvMouseButton_Left)
    if not dpg.does_item_exist(_DRAWLIST_TAG) or not dpg.does_item_exist(_CURSOR_LAYER):
        return

    hovered = dpg.is_item_hovered(_DRAWLIST_TAG)
    active = _dragging or _drag_clip is not None

    # Relâchement du bouton
    if not btn_down:
        if _drag_clip is not None:
            rearranged = False
            for row_idx, row in enumerate(_tracks):
                if _drag_clip in row:
                    row.sort(key=lambda c: c.timeline_start)
                    if _has_overlap(_drag_clip, row):
                        row.remove(_drag_clip)
                        if row:
                            _tracks.insert(row_idx, [_drag_clip])  # nouvelle piste au-dessus
                        else:
                            _tracks[row_idx] = [_drag_clip]  # remplace piste vide
                        rearranged = True
                    break
            if rearranged:
                if _on_track_reordered is not None:
                    _on_track_reordered()
                _redraw()
            else:
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

        # Début d'un drag
        if hovered and btn_down and not active:
            clip = _clip_at(local_x, local_y)
            if clip is not None:
                _drag_clip = clip
                _drag_offset_px = local_x - clip.timeline_start * _px_per_sec
                if _selected_clip is not clip:
                    _selected_clip = clip
                    _redraw_static_only()
                    if _on_select is not None:
                        _on_select(clip)
            else:
                _selected_clip = None
                _dragging = True

        # Drag d'un clip
        if _drag_clip is not None and btn_down:
            _drag_clip.timeline_start = max(0.0, (local_x - _drag_offset_px) / _px_per_sec)
            _redraw_static_only()

        # Seek drag
        elif _dragging and btn_down and _on_seek is not None:
            _on_seek(max(0.0, local_x / _px_per_sec))

        # Curseur hover
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


def _move_track(row: int, direction: int) -> None:
    target = row + direction
    if not 0 <= target < len(_tracks):
        return
    _tracks[row], _tracks[target] = _tracks[target], _tracks[row]
    if _on_track_reordered is not None:
        _on_track_reordered()
    _redraw()


def _clip_at(local_x: float, local_y: float) -> "MediaClip | None":
    clip_h = _TRACK_H - 8
    for row_idx, row in enumerate(_tracks):
        clip_y = _RULER_H + row_idx * _TRACK_H + 4
        if not (clip_y <= local_y <= clip_y + clip_h):
            continue
        for clip in row:
            x = clip.timeline_start * _px_per_sec
            w = max(2.0, clip.duration * _px_per_sec)
            if x <= local_x <= x + w:
                return clip
    return None


def _has_overlap(clip: MediaClip, row: list[MediaClip]) -> bool:
    for other in row:
        if other is clip:
            continue
        if clip.timeline_start < other.timeline_end and clip.timeline_end > other.timeline_start:
            return True
    return False


def _all_clips() -> list[MediaClip]:
    return [c for row in _tracks for c in row]


# ── Zoom ──────────────────────────────────────────────────────────────────────

def _set_zoom_index(index: int) -> None:
    global _zoom_idx, _px_per_sec
    _zoom_idx = index
    _px_per_sec = _ZOOM_LEVELS[_zoom_idx]
    _redraw()
    if _on_zoom is not None:
        _on_zoom(_px_per_sec)


def _zoom_in() -> None:
    if _zoom_idx < len(_ZOOM_LEVELS) - 1:
        _set_zoom_index(_zoom_idx + 1)


def _zoom_out() -> None:
    if _zoom_idx > 0:
        _set_zoom_index(_zoom_idx - 1)


# ── Taille ────────────────────────────────────────────────────────────────────

def _content_height() -> int:
    return _RULER_H + max(1, len(_tracks)) * _TRACK_H


def _content_width() -> int:
    scroll_w = dpg.get_item_rect_size(_SCROLL_TAG)[0] if dpg.does_item_exist(_SCROLL_TAG) else 0
    all_clips = _all_clips()
    if not all_clips:
        return max(_MIN_CONTENT_W, scroll_w)
    max_end = max(c.timeline_end for c in all_clips)
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
    if not _all_clips():
        return
    w = _content_width()
    dpg.configure_item(_DRAWLIST_TAG, width=w, height=_content_height())
    _draw_ruler(w)
    _draw_clips()
    _redraw_playhead()


def _redraw_static_only() -> None:
    """Redessine règle + clips sans reconstruire les headers."""
    if not dpg.does_item_exist(_STATIC_LAYER) or not _all_clips():
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
    n = len(_tracks)
    for i, row in enumerate(_tracks):
        with dpg.child_window(
            height=_TRACK_H,
            width=-1,
            border=False,
            no_scrollbar=True,
            parent=_HEADERS_TAG,
        ):
            dpg.add_spacer(height=4)
            with dpg.group(horizontal=True):
                # Colonne gauche : ▲ / ▼ empilés
                with dpg.group(indent=2):
                    up_btn = dpg.add_button(
                        label="▲", width=18, height=18,
                        callback=_on_move_up_btn, user_data=i,
                    )
                    down_btn = dpg.add_button(
                        label="▼", width=18, height=18,
                        callback=_on_move_down_btn, user_data=i,
                    )
                # Colonne droite : nom + bouton ×
                with dpg.group():
                    if len(row) == 1:
                        label = _truncate(row[0].media.path.stem, _HEADER_W - 36)
                    else:
                        label = f"Piste {i + 1} ({len(row)} clips)"
                    dpg.add_text(label)
                    dpg.add_button(
                        label="×", width=18, height=18,
                        callback=_on_delete_track_btn, user_data=i,
                    )
            if i == 0:
                dpg.configure_item(up_btn, show=False)
            if i == n - 1:
                dpg.configure_item(down_btn, show=False)


def _on_move_up_btn(sender, app_data, row: int) -> None:
    _move_track(row, -1)


def _on_move_down_btn(sender, app_data, row: int) -> None:
    _move_track(row, +1)


def _on_delete_track_btn(sender, app_data, track_idx: int) -> None:
    if 0 <= track_idx < len(_tracks):
        _confirm_delete_track(track_idx)


def _confirm_delete_track(track_idx: int) -> None:
    dialog_tag = "timeline_confirm_delete"
    if dpg.does_item_exist(dialog_tag):
        dpg.delete_item(dialog_tag)

    row = _tracks[track_idx]
    if len(row) == 1:
        msg = f'Supprimer « {row[0].media.path.stem} » de la timeline ?'
    else:
        msg = f'Supprimer la piste et ses {len(row)} clips de la timeline ?'

    w, h = 320, 110
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
        dpg.add_text(msg)
        dpg.add_spacer(height=8)
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Supprimer",
                width=100,
                callback=lambda: _do_delete_track(track_idx, dialog_tag),
            )
            dpg.add_button(
                label="Annuler",
                width=80,
                callback=lambda: dpg.delete_item(dialog_tag),
            )


def _do_delete_track(track_idx: int, dialog_tag: str) -> None:
    dpg.delete_item(dialog_tag)
    if not (0 <= track_idx < len(_tracks)):
        return
    clips_to_delete = list(_tracks[track_idx])
    del _tracks[track_idx]
    if _on_delete is not None:
        for clip in clips_to_delete:
            _on_delete(clip)
    _redraw()


def _draw_ruler(total_w: int) -> None:
    dpg.draw_rectangle(
        (0, 0), (total_w, _RULER_H),
        fill=_COLOR_RULER_BG,
        color=(0, 0, 0, 0),
        parent=_STATIC_LAYER,
    )
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

    for row_idx, row in enumerate(_tracks):
        clip_y = _RULER_H + row_idx * _TRACK_H + 4
        for clip in row:
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

        if getattr(clip, "effects", ()) and w >= 24:
            # Badge « fx » : le clip porte au moins un effet.
            bx = x + w - 22
            dpg.draw_rectangle(
                (bx, clip_y + 3), (bx + 19, clip_y + 16),
                fill=_COLOR_FX_BADGE, color=(0, 0, 0, 0), rounding=3,
                parent=_STATIC_LAYER,
            )
            dpg.draw_text((bx + 4, clip_y + 3), "fx", color=_COLOR_CLIP_TEXT, size=12,
                          parent=_STATIC_LAYER)

        if getattr(clip, "effects", ()) and w >= 24:
            # Badge « fx » : le clip porte au moins un effet.
            bx = x + w - 22
            dpg.draw_rectangle(
                (bx, clip_y + 3), (bx + 19, clip_y + 16),
                fill=_COLOR_FX_BADGE, color=(0, 0, 0, 0), rounding=3,
                parent=_STATIC_LAYER,
            )
            dpg.draw_text((bx + 4, clip_y + 3), "fx", color=_COLOR_CLIP_TEXT, size=12,
                          parent=_STATIC_LAYER)


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
