"""Panneau timeline : règle, pistes et clips."""

import dearpygui.dearpygui as dpg

from makitop.media.thumbnails import THUMB_H, THUMB_W
from makitop.model.keyframes import PROPERTIES
from makitop.model.timeline import BaseClip, TextClip

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
_GHOST_LAYER = "timeline_ghost_layer"
_PLAYHEAD_LAYER = "timeline_playhead_layer"
_CURSOR_LAYER = "timeline_cursor_layer"

# ── Dimensions ────────────────────────────────────────────────────────────────
_HEADER_W = 130     # largeur colonne labels (gauche, fixe)
_RULER_H = 24       # hauteur de la règle temporelle
_TRACK_H = 60       # hauteur d'une piste
_MIN_CONTENT_W = 800

# ── Zoom ──────────────────────────────────────────────────────────────────────
_ZOOM_LEVELS = [1, 2, 3, 4, 5, 6, 8, 10, 13, 16, 20, 25, 32, 40, 50, 63, 80, 100,
                125, 155, 195, 245, 275, 310, 350, 390]
_DEFAULT_ZOOM_IDX = 17  # 100 px/s par défaut
_zoom_idx: int = _DEFAULT_ZOOM_IDX
_px_per_sec: int = _ZOOM_LEVELS[_DEFAULT_ZOOM_IDX]

# ── Couleurs ──────────────────────────────────────────────────────────────────
_COLOR_RULER_BG = (28, 28, 32, 255)
_COLOR_TICK = (120, 120, 130, 255)
_COLOR_TICK_LABEL = (170, 170, 180, 255)
_COLOR_CLIP_FILL = (50, 110, 170, 210)
_COLOR_CLIP_BORDER = (90, 150, 210, 255)
_COLOR_TEXT_FILL = (105, 64, 158, 235)
_COLOR_TEXT_BORDER = (175, 126, 221, 255)
_COLOR_CLIP_SELECTED = (255, 200, 60, 255)
_COLOR_CLIP_TEXT = (220, 225, 235, 255)
_COLOR_FX_BADGE = (140, 90, 220, 230)
_COLOR_KEY_BADGE = (30, 110, 145, 245)
_COLOR_PLAYHEAD = (210, 60, 60, 255)
_COLOR_CURSOR = (255, 255, 255, 55)

# ── État ──────────────────────────────────────────────────────────────────────
# _tracks[0] = piste en haut (priorité la plus haute dans le lecteur)
_tracks: list[list[BaseClip]] = []
_playhead_sec: float = 0.0
_on_seek = None            # Callable[[float], None]
_on_delete = None          # Callable[[MediaClip], None]
_on_split = None           # Callable[[], None]
_on_duplicate = None       # Callable[[], None]
_on_copy = None            # Callable[[], None]
_on_cut = None             # Callable[[], None]
_on_paste = None           # Callable[[], None]
_on_drag_start = None      # Callable[[], None]
_on_clip_moved = None      # Callable[[MediaClip], None]  — drag d'un clip
_on_track_reordered = None # Callable[[], None]           — réordonnancement ▲/▼
_on_select = None          # Callable[[MediaClip], None]
_on_zoom = None            # Callable[[int], None]        — nouveau zoom en px/s
_dragging: bool = False
_drag_clip: BaseClip | None = None
_drag_offset_px: float = 0.0
_drag_source_row: int | None = None
_selected_clip: BaseClip | None = None
_pending_fit_zoom: bool = False
_show_keyframes = False
_selected_keyframe = None
_drag_keyframe = None  # (propriété, temps initial, temps provisoire)
_on_key_select = None
_on_key_move = None
_KEY_ROW_H = 22
_KEY_COLOR = (105, 210, 245, 255)
_get_dragging_media = None   # Callable[[], Media | None]
_on_media_drop = None        # Callable[[Media, float, int], None]
_get_dragging_text = None    # Callable[[], str | None]
_on_text_drop = None         # Callable[[str, float], None]


def create() -> None:
    global _zoom_idx, _px_per_sec, _tracks, _playhead_sec
    global _dragging, _drag_clip, _drag_offset_px, _drag_source_row, _selected_clip
    global _on_delete, _on_clip_moved, _on_track_reordered, _on_select, _on_zoom, _pending_fit_zoom
    global _show_keyframes, _selected_keyframe, _drag_keyframe
    global _on_key_select, _on_key_move
    _show_keyframes = False
    _selected_keyframe = _drag_keyframe = None
    _on_key_select = _on_key_move = None
    _zoom_idx = _DEFAULT_ZOOM_IDX
    _px_per_sec = _ZOOM_LEVELS[_DEFAULT_ZOOM_IDX]
    _tracks = []
    _playhead_sec = 0.0
    _dragging = False
    _drag_clip = None
    _drag_offset_px = 0.0
    _drag_source_row = None
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
            # ── Bloc 1 : Zoom ──────────────────────────────────────────────────
            dpg.add_button(label="-", tag="timeline_zoom_out", width=24, height=22,
                           callback=_zoom_out)
            with dpg.tooltip("timeline_zoom_out"):
                dpg.add_text("Zoom arrière  [Ctrl+-]")
            dpg.add_button(label="+", tag="timeline_zoom_in", width=24, height=22,
                           callback=_zoom_in)
            with dpg.tooltip("timeline_zoom_in"):
                dpg.add_text("Zoom avant  [Ctrl++]")
            dpg.add_separator()
            # ── Bloc 2 : Presse-papier & sélection ────────────────────────────
            dpg.add_button(label="Copier", tag="timeline_copy_clip", enabled=False,
                           callback=_copy_selected)
            with dpg.tooltip("timeline_copy_clip"):
                dpg.add_text("Copier le clip sélectionné  [Ctrl+C]")
            dpg.add_button(label="Coller", tag="timeline_paste_clip",
                           callback=_paste_clip)
            with dpg.tooltip("timeline_paste_clip"):
                dpg.add_text("Coller le clip copié au playhead  [Ctrl+V]")
            dpg.add_button(label="Couper", tag="timeline_cut_clip",
                           enabled=False, callback=_cut_selected)
            with dpg.tooltip("timeline_cut_clip"):
                dpg.add_text("Couper le clip sélectionné  [Ctrl+X]")
            dpg.add_button(label="Dupliquer", tag="timeline_duplicate_clip", enabled=False,
                           callback=_duplicate_selected)
            with dpg.tooltip("timeline_duplicate_clip"):
                dpg.add_text("Dupliquer le clip sélectionné  [Ctrl+D]")
            dpg.add_button(label="Supprimer", tag="timeline_delete_clip", enabled=False,
                           callback=delete_selected)
            with dpg.tooltip("timeline_delete_clip"):
                dpg.add_text("Supprimer le clip sélectionné  [Suppr]")
            dpg.add_separator()
            # ── Bloc 3 : Outils timeline ───────────────────────────────────────
            dpg.add_button(label="Découper", tag="timeline_split_clip",
                           callback=_split_at_playhead)
            with dpg.tooltip("timeline_split_clip"):
                dpg.add_text("Découper le clip à la position de lecture  [Ctrl+B]")
            dpg.add_separator()
            dpg.add_button(label="↩ Annuler", tag="timeline_undo", enabled=False,
                           callback=_do_undo)
            with dpg.tooltip("timeline_undo"):
                dpg.add_text("Annuler la dernière action  [Ctrl+Z]")
            dpg.add_button(label="↪ Rétablir", tag="timeline_redo", enabled=False,
                           callback=_do_redo)
            with dpg.tooltip("timeline_redo"):
                dpg.add_text("Rétablir  [Ctrl+Y]")
            dpg.add_separator()
            dpg.add_checkbox(label="Images clés", default_value=_show_keyframes,
                             tag="timeline_show_keyframes", callback=_toggle_keyframes)
            with dpg.tooltip("timeline_show_keyframes"):
                dpg.add_text("Afficher/masquer les images clés  [Ctrl+K]")
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
                dpg.add_spacer(height=_RULER_H)
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
                dpg.add_draw_layer(tag=_GHOST_LAYER, parent=_DRAWLIST_TAG)
                dpg.add_draw_layer(tag=_PLAYHEAD_LAYER, parent=_DRAWLIST_TAG)
                dpg.add_draw_layer(tag=_CURSOR_LAYER, parent=_DRAWLIST_TAG)

    with dpg.theme() as headers_theme, dpg.theme_component(dpg.mvAll):
        dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 0)
    dpg.bind_item_theme(_HEADERS_TAG, headers_theme)
    dpg.bind_item_handler_registry(TAG, _HANDLER_TAG)


def add_clip(clip: BaseClip) -> None:
    """Ajoute un clip dans la piste correspondante (créée si inexistante)."""
    _insert_clip(clip)
    _redraw()


def _insert_clip(clip: BaseClip) -> None:
    order = clip.track
    for row in _tracks:
        if row[0].track == order:
            row.append(clip)
            row.sort(key=lambda c: c.timeline_start)
            return
    for i, row in enumerate(_tracks):
        if row[0].track < order:
            _tracks.insert(i, [clip])
            return
    _tracks.append([clip])


def set_clips(clips, selected_id, selected_keyframe) -> None:
    _tracks.clear()
    for clip in clips:
        _insert_clip(clip)
    set_selected(selected_id, selected_keyframe)


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


def bind_split(fn) -> None:
    global _on_split
    _on_split = fn


def _split_at_playhead() -> None:
    if _on_split is not None:
        _on_split()


def bind_duplicate(fn) -> None:
    global _on_duplicate
    _on_duplicate = fn


def _duplicate_selected() -> None:
    if _on_duplicate is not None:
        _on_duplicate()


def bind_clip_drag_start(fn) -> None:
    global _on_drag_start
    _on_drag_start = fn


_on_undo = None            # Callable[[], None]
_on_redo = None            # Callable[[], None]


def bind_undo(fn) -> None:
    global _on_undo
    _on_undo = fn


def bind_redo(fn) -> None:
    global _on_redo
    _on_redo = fn


def _do_undo() -> None:
    if _on_undo is not None:
        _on_undo()


def _do_redo() -> None:
    if _on_redo is not None:
        _on_redo()


def update_undo_redo_buttons(can_undo: bool, can_redo: bool) -> None:
    if dpg.does_item_exist("timeline_undo"):
        dpg.configure_item("timeline_undo", enabled=can_undo)
    if dpg.does_item_exist("timeline_redo"):
        dpg.configure_item("timeline_redo", enabled=can_redo)


def bind_copy(fn) -> None:
    global _on_copy
    _on_copy = fn


def bind_cut(fn) -> None:
    global _on_cut
    _on_cut = fn


def bind_paste(fn) -> None:
    global _on_paste
    _on_paste = fn


def _copy_selected() -> None:
    if _on_copy is not None:
        _on_copy()


def _cut_selected() -> None:
    if _on_cut is not None:
        _on_cut()


def _paste_clip() -> None:
    if _on_paste is not None:
        _on_paste()


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


def bind_get_dragging_media(fn) -> None:
    global _get_dragging_media
    _get_dragging_media = fn


def bind_media_drop(fn) -> None:
    global _on_media_drop
    _on_media_drop = fn


def bind_get_dragging_text(fn) -> None:
    global _get_dragging_text
    _get_dragging_text = fn


def bind_text_drop(fn) -> None:
    global _on_text_drop
    _on_text_drop = fn


def bind_keyframes(on_select, on_move):
    global _on_key_select, _on_key_move
    _on_key_select, _on_key_move = on_select, on_move


def _toggle_keyframes(sender, value):
    global _show_keyframes
    _show_keyframes = value
    _redraw()


def set_zoom(pixels_per_second: int) -> None:
    """Applique un zoom enregistré (niveau le plus proche), sans notifier l'éditeur."""
    global _zoom_idx, _px_per_sec
    _zoom_idx = min(range(len(_ZOOM_LEVELS)),
                    key=lambda i: abs(_ZOOM_LEVELS[i] - pixels_per_second))
    _px_per_sec = _ZOOM_LEVELS[_zoom_idx]
    _redraw()


def set_selected(clip_id: str | None, keyframe=None) -> None:
    global _selected_clip, _selected_keyframe
    _selected_clip = next((c for c in _all_clips() if c.id == clip_id), None) if clip_id else None
    _selected_keyframe = keyframe
    for tag in ("timeline_delete_clip", "timeline_duplicate_clip",
                "timeline_copy_clip", "timeline_cut_clip"):
        if dpg.does_item_exist(tag):
            dpg.configure_item(tag, enabled=_selected_clip is not None)
    _redraw()


def delete_selected() -> None:
    if _selected_clip is not None and _on_delete is not None:
        _on_delete(_selected_clip)


def set_playhead(seconds: float) -> None:
    global _playhead_sec
    _playhead_sec = seconds
    _redraw_playhead()


# ── Tick (appelé chaque frame) ────────────────────────────────────────────────

def tick() -> None:
    global _dragging, _drag_clip, _drag_offset_px, _drag_source_row, _selected_clip
    global _drag_keyframe
    if _pending_fit_zoom:
        _apply_fit_zoom()
    if dpg.does_item_exist(_GHOST_LAYER):
        dpg.delete_item(_GHOST_LAYER, children_only=True)

    # Étendre le drawlist pendant un drag externe pour autoriser le drop en bas
    ext_active = _get_dragging_media is not None and _get_dragging_media() is not None
    if dpg.does_item_exist(_DRAWLIST_TAG):
        target_h = _content_height() + (_TRACK_H if ext_active else 0)
        if dpg.get_item_rect_size(_DRAWLIST_TAG)[1] != target_h:
            dpg.configure_item(_DRAWLIST_TAG, height=target_h)

    btn_down = dpg.is_mouse_button_down(dpg.mvMouseButton_Left)
    if not dpg.does_item_exist(_DRAWLIST_TAG) or not dpg.does_item_exist(_CURSOR_LAYER):
        return
    scroll_y = dpg.get_y_scroll(_SCROLL_TAG)
    if dpg.get_y_scroll(_HEADERS_TAG) != scroll_y:
        dpg.set_y_scroll(_HEADERS_TAG, scroll_y)

    hovered = dpg.is_item_hovered(_DRAWLIST_TAG)
    active = _dragging or _drag_clip is not None or _drag_keyframe is not None

    # Relâchement du bouton
    if not btn_down:
        if _drag_keyframe is not None:
            property, old_time, new_time = _drag_keyframe
            _drag_keyframe = None
            if new_time != old_time and _on_key_move:
                _on_key_move(property, old_time, new_time)
            _redraw_static_only()
        if _drag_clip is not None:
            dest_row_idx = next((i for i, row in enumerate(_tracks) if _drag_clip in row), None)
            reorder_needed = dest_row_idx != _drag_source_row
            # Si la row de destination a plusieurs clips, un merge a eu lieu (les indices
            # ont pu se décaler après un pop() pendant le drag) → forcer le reorder
            if not reorder_needed and dest_row_idx is not None and len(_tracks[dest_row_idx]) > 1:
                reorder_needed = True
            if dest_row_idx is not None:
                row = _tracks[dest_row_idx]
                row.sort(key=lambda c: c.timeline_start)
                if _has_overlap(_drag_clip, row):
                    row.remove(_drag_clip)
                    # Un clip descendu sur une piste occupée passe derrière cette piste.
                    insert_at = dest_row_idx + int(_drag_clip.track > row[0].track)
                    _tracks.insert(insert_at, [_drag_clip])
                    reorder_needed = True
            if reorder_needed:
                if _on_track_reordered is not None:
                    _on_track_reordered()
                _redraw()
            else:
                if _on_clip_moved is not None:
                    _on_clip_moved(_drag_clip)
            _drag_clip = None
            _drag_source_row = None
        _dragging = False

    if hovered or active:
        mx, my = dpg.get_mouse_pos(local=False)
        dl_state = dpg.get_item_state(_DRAWLIST_TAG)
        if "rect_min" not in dl_state:
            return
        dl_min = dl_state["rect_min"]
        local_x = mx - dl_min[0]
        local_y = my - dl_min[1]

        # Début d'un drag — bloqué si un média externe est en cours de drop
        _external_drag = (
            (_get_dragging_media is not None and _get_dragging_media() is not None)
            or (_get_dragging_text is not None and _get_dragging_text() is not None)
        )
        if hovered and btn_down and not active and not _external_drag:
            key = _keyframe_at(local_x, local_y)
            clip = _clip_at(local_x, local_y)
            if key is not None:
                _drag_keyframe = (key.property, key.time, key.time)
                if _on_key_select:
                    _on_key_select(_selected_clip.id, key.property, key.time)
            elif clip is not None:
                if _on_drag_start is not None:
                    _on_drag_start()
                _drag_clip = clip
                _drag_offset_px = local_x - clip.timeline_start * _px_per_sec
                _drag_source_row = next(
                    (i for i, row in enumerate(_tracks) if clip in row), None
                )
                if _selected_clip is not clip:
                    _selected_clip = clip
                    _redraw_static_only()
                    if _on_select is not None:
                        _on_select(clip)
            else:
                # Un seek dans une ligne d'animation conserve le clip sélectionné.
                _dragging = True

        # Drag d'un clip
        if _drag_keyframe is not None and btn_down and _selected_clip is not None:
            property, old_time, _ = _drag_keyframe
            time = max(0, min(_selected_clip.duration,
                              local_x / _px_per_sec - _selected_clip.timeline_start))
            if abs(time - old_time) * _px_per_sec < 3:
                time = old_time
            if time != _drag_keyframe[2]:
                _drag_keyframe = (property, old_time, time)
                _redraw_static_only()
        elif _drag_clip is not None and btn_down:
            new_start = max(0.0, (local_x - _drag_offset_px) / _px_per_sec)

            # Déplacement vertical entre pistes
            target_row = min(_row_at(local_y), len(_tracks) - 1)
            current_row = next((i for i, row in enumerate(_tracks) if _drag_clip in row), None)
            if current_row is not None and target_row != current_row:
                _tracks[current_row].remove(_drag_clip)
                if not _tracks[current_row]:
                    _tracks.pop(current_row)
                    if target_row > current_row:
                        target_row -= 1
                target_row = max(0, min(len(_tracks) - 1, target_row))
                _drag_clip.timeline_start = new_start
                _tracks[target_row].append(_drag_clip)
                _tracks[target_row].sort(key=lambda c: c.timeline_start)
                _redraw()
            else:
                _drag_clip.timeline_start = new_start
                _redraw_static_only()

            # Ghost : surbrillance de la piste cible + indicateur si overlap
            _draw_drag_ghost(target_row, new_start)

        # Seek drag
        elif _dragging and btn_down and _on_seek is not None and not _external_drag:
            _on_seek(max(0.0, local_x / _px_per_sec))

        # Drop d'un média externe dans la timeline
        if _external_drag and hovered:
            ext_media = _get_dragging_media()
            if ext_media is not None:
                ext_start = max(0.0, local_x / _px_per_sec)
                ext_row = _row_at(local_y)
                _draw_external_media_ghost(ext_media, ext_start, ext_row)
                if not btn_down and _on_media_drop is not None:
                    _on_media_drop(ext_media, ext_start, ext_row)

        # Drop d'un préréglage de texte dans la timeline
        ext_text = _get_dragging_text() if _get_dragging_text is not None else None
        if ext_text is not None and hovered:
            ext_start = max(0.0, local_x / _px_per_sec)
            if not btn_down and _on_text_drop is not None:
                _on_text_drop(ext_text, ext_start)

        # Curseur hover
        dpg.delete_item(_CURSOR_LAYER, children_only=True)
        if hovered and _drag_clip is None and not _external_drag and local_x >= 0:
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
    if not (0 <= row < len(_tracks) and 0 <= target < len(_tracks)):
        return
    _tracks[row], _tracks[target] = _tracks[target], _tracks[row]
    if _on_track_reordered is not None:
        _on_track_reordered()
    _redraw()


def move_track_to(from_row: int, to_row: int) -> None:
    """Déplace une piste de from_row vers to_row (sans déclencher les callbacks)."""
    if from_row == to_row:
        return
    if not (0 <= from_row < len(_tracks) and 0 <= to_row < len(_tracks)):
        return
    row = _tracks.pop(from_row)
    _tracks.insert(to_row, row)


def _clip_at(local_x: float, local_y: float) -> BaseClip | None:
    clip_h = _TRACK_H - 8
    for row_idx, row in enumerate(_tracks):
        clip_y = _row_top(row_idx) + 4
        if not (clip_y <= local_y <= clip_y + clip_h):
            continue
        for clip in row:
            x = clip.timeline_start * _px_per_sec
            w = max(2.0, clip.duration * _px_per_sec)
            if x <= local_x <= x + w:
                return clip
    return None


def _has_overlap(clip: BaseClip, row: list[BaseClip]) -> bool:
    for other in row:
        if other is clip:
            continue
        if clip.timeline_start < other.timeline_end and clip.timeline_end > other.timeline_start:
            return True
    return False


def _all_clips() -> list[BaseClip]:
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


def zoom_in() -> None:
    _zoom_in()


def zoom_out() -> None:
    _zoom_out()


def toggle_keyframes() -> None:
    if dpg.does_item_exist("timeline_show_keyframes"):
        new_val = not dpg.get_value("timeline_show_keyframes")
        dpg.set_value("timeline_show_keyframes", new_val)
        _toggle_keyframes(None, new_val)


# ── Taille ────────────────────────────────────────────────────────────────────

def _content_height() -> int:
    return _RULER_H + (sum(_row_height(i) for i in range(len(_tracks))) or _TRACK_H)


def _expanded(row_idx):
    return (_show_keyframes and _selected_clip is not None
            and (not isinstance(_selected_clip, TextClip) or bool(_selected_clip.keyframes))
            and any(c.id == _selected_clip.id for c in _tracks[row_idx]))


def _row_height(row_idx):
    return _TRACK_H + (len(_selected_clip.keyframe_properties) * _KEY_ROW_H + 12
                       if _expanded(row_idx) else 0)


def _row_top(row_idx):
    return _RULER_H + sum(_row_height(i) for i in range(row_idx))


def _row_at(y):
    top = _RULER_H
    for i in range(len(_tracks)):
        top += _row_height(i)
        if y < top:
            return i
    return len(_tracks)


def _key_positions():
    if _selected_clip is None:
        return
    clip = _selected_clip
    for index in range(len(_tracks)):
        if not _expanded(index):
            continue
        top = _row_top(index) + _TRACK_H + 10
        for key in clip.keyframes:
            if key.time > clip.duration or key.property not in clip.keyframe_properties:
                continue
            time = key.time
            if _drag_keyframe and (key.property, key.time) == _drag_keyframe[:2]:
                time = _drag_keyframe[2]
            x = (clip.timeline_start + time) * _px_per_sec
            y = top + clip.keyframe_properties.index(key.property) * _KEY_ROW_H
            yield key, x, y


def _keyframe_at(x, y):
    return next((key for key, kx, ky in _key_positions()
                 if abs(x - kx) + abs(y - ky) <= 10), None)


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
    w = _content_width()
    dpg.configure_item(_DRAWLIST_TAG, width=w, height=_content_height())
    _draw_ruler(w)
    if _tracks:
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
    dpg.add_spacer(height=_RULER_H, parent=_HEADERS_TAG)
    for i, row in enumerate(_tracks):
        with dpg.child_window(
            height=_row_height(i),
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
                    if all(isinstance(clip, TextClip) for clip in row):
                        label = f"Texte · {row[0].track + 1}"
                    elif len(row) == 1:
                        label = _truncate(row[0].label, _HEADER_W - 36)
                    else:
                        label = f"Piste {i + 1} ({len(row)} clips)"
                    dpg.add_text(label)
                    dpg.add_button(
                        label="×", width=18, height=18,
                        callback=_on_delete_track_btn, user_data=i,
                    )
            if i == 0:
                dpg.configure_item(up_btn, show=False)
            if i == len(_tracks) - 1:
                dpg.configure_item(down_btn, show=False)
            if _expanded(i):
                names = _selected_clip.keyframe_properties
                with dpg.drawlist(width=_HEADER_W - 10, height=len(names) * _KEY_ROW_H,
                                  pos=(4, _TRACK_H + 2)):
                    for j, name in enumerate(names):
                        dpg.draw_text((0, j * _KEY_ROW_H), PROPERTIES[name][0],
                                      color=_KEY_COLOR, size=12)
    # Réserve la place de la barre horizontale pour garder les en-têtes alignés en bas.
    dpg.add_spacer(height=14, parent=_HEADERS_TAG)


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
        name = _truncate(row[0].label, 160)
        msg = f'Supprimer « {name} » de la timeline ?'
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


def _draw_drag_ghost(target_row: int, new_start: float) -> None:
    if not dpg.does_item_exist(_GHOST_LAYER) or _drag_clip is None:
        return
    total_w = _content_width()
    row_y = _row_top(target_row)

    # Surbrillance de la piste cible
    dpg.draw_rectangle(
        (0, row_y), (total_w, row_y + _TRACK_H),
        fill=(255, 255, 255, 12),
        color=(160, 190, 255, 60),
        thickness=1,
        parent=_GHOST_LAYER,
    )

    # Si la position actuelle provoquerait un overlap → ligne jaune = future nouvelle piste
    dest_row_clips = _tracks[target_row] if 0 <= target_row < len(_tracks) else []
    if _has_overlap(_drag_clip, dest_row_clips):
        dpg.draw_line(
            (0, row_y), (total_w, row_y),
            color=(255, 210, 50, 220),
            thickness=2,
            parent=_GHOST_LAYER,
        )
        dpg.draw_text(
            (4, row_y + 2),
            "Nouvelle piste",
            color=(255, 210, 50, 200),
            size=11,
            parent=_GHOST_LAYER,
        )



def _draw_external_media_ghost(media, start: float, target_row: int) -> None:
    """Ghost vert à la position d'insertion calculée depuis la souris."""
    if not dpg.does_item_exist(_GHOST_LAYER):
        return
    total_w = _content_width()
    insert_y = _row_top(target_row)

    # Ligne d'insertion horizontale
    dpg.draw_line(
        (0, insert_y), (total_w, insert_y),
        color=(80, 220, 120, 220),
        thickness=2,
        parent=_GHOST_LAYER,
    )
    # Ghost clip à la position d'insertion
    gx = int(start * _px_per_sec)
    duration = getattr(media, "duration", None) or 10.0
    gw = max(10, int(duration * _px_per_sec))
    clip_h = _TRACK_H - 8
    gy = insert_y + 4
    dpg.draw_rectangle(
        (gx, gy), (gx + gw, gy + clip_h),
        fill=(80, 200, 100, 55),
        color=(80, 220, 120, 200),
        thickness=2,
        parent=_GHOST_LAYER,
    )
    if gw >= 40:
        dpg.draw_text(
            (gx + 5, gy + clip_h // 2 - 6),
            media.path.stem,
            color=(200, 255, 210, 220),
            size=12,
            parent=_GHOST_LAYER,
        )


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
        clip_y = _row_top(row_idx) + 4
        for clip in row:
            x = int(clip.timeline_start * _px_per_sec)
            w = max(2, int(clip.duration * _px_per_sec))

            is_text = isinstance(clip, TextClip)
            border = _COLOR_TEXT_BORDER if is_text else _COLOR_CLIP_BORDER
            if clip is _selected_clip:
                border = _COLOR_CLIP_SELECTED
            dpg.draw_rectangle(
                (x, clip_y), (x + w, clip_y + clip_h),
                fill=_COLOR_TEXT_FILL if is_text else _COLOR_CLIP_FILL,
                color=border,
                thickness=2 if clip is _selected_clip else 1,
                parent=_STATIC_LAYER,
            )

            texture_tag = None if is_text else f"texture_{clip.media.id}"
            if texture_tag and w >= 8 and dpg.does_item_exist(texture_tag):
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
                    _truncate(clip.label, w - 10),
                    color=_COLOR_CLIP_TEXT,
                    size=12,
                    parent=_STATIC_LAYER,
                )

            _draw_clip_badges(clip, x, clip_y, w)
    _draw_keyframes()


def _draw_clip_badges(clip: BaseClip, x: int, y: int, width: int) -> None:
    """Badges compacts en haut à droite, par clip (même si les lignes sont masquées)."""
    if width < 24:
        return
    has_keys = bool(clip.keyframes)
    has_effects = bool(getattr(clip, "effects", ()))
    if not has_keys and not has_effects:
        return
    # Sur un clip court, privilégier l'animation ; éviter deux badges superposés.
    show_fx = has_effects and (not has_keys or width >= 44)
    bx = x + width - 22
    if has_keys:
        dpg.draw_rectangle((bx, y + 3), (bx + 19, y + 16),
                           fill=_COLOR_KEY_BADGE, color=(0, 0, 0, 0), rounding=3,
                           parent=_STATIC_LAYER)
        dpg.draw_quad((bx + 9, y + 5), (bx + 13, y + 9),
                      (bx + 9, y + 13), (bx + 5, y + 9),
                      fill=_COLOR_CLIP_TEXT, color=_COLOR_CLIP_TEXT,
                      parent=_STATIC_LAYER, tag=f"key_badge_{clip.id}")
        bx -= 22
    if show_fx:
        dpg.draw_rectangle((bx, y + 3), (bx + 19, y + 16),
                           fill=_COLOR_FX_BADGE, color=(0, 0, 0, 0), rounding=3,
                           parent=_STATIC_LAYER)
        dpg.draw_text((bx + 4, y + 3), "fx", color=_COLOR_CLIP_TEXT, size=12,
                      parent=_STATIC_LAYER, tag=f"fx_badge_{clip.id}")


def _draw_keyframes():
    if _selected_clip is None:
        return
    clip = _selected_clip
    for index in range(len(_tracks)):
        if not _expanded(index):
            continue
        top = _row_top(index) + _TRACK_H
        left = clip.timeline_start * _px_per_sec
        right = clip.timeline_end * _px_per_sec
        count = len(clip.keyframe_properties)
        dpg.draw_rectangle((left, top), (right, top + count * _KEY_ROW_H + 10),
                           fill=(25, 35, 48, 255), color=(55, 75, 95, 255), parent=_STATIC_LAYER)
        for i in range(count):
            y = top + 10 + i * _KEY_ROW_H
            dpg.draw_line((left, y), (right, y), color=(60, 80, 100, 255), parent=_STATIC_LAYER)
    for key, x, y in _key_positions():
        color = (_COLOR_CLIP_SELECTED if (key.property, key.time) == _selected_keyframe
                 else _KEY_COLOR)
        dpg.draw_quad((x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y),
                      fill=color, color=(245, 245, 255, 255), parent=_STATIC_LAYER,
                      tag=f"keyframe_{clip.id}_{key.property}_{key.time}")

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
    def text_width(value):
        size = dpg.get_text_size(value) if dpg.is_viewport_ok() else None
        return size[0] if size else len(value) * 7

    if text_width(text) <= max_px:
        return text
    ellipsis = "…"
    text = text[:int(max_px // 3)]
    while text and text_width(text + ellipsis) > max_px:
        text = text[:-1]
    return (text + ellipsis) if text else ellipsis
