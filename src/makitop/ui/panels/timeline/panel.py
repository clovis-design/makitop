"""Panneau timeline : règle, pistes et clips."""

from dataclasses import replace

import dearpygui.dearpygui as dpg

from makitop.media.thumbnails import THUMB_H, THUMB_W
from makitop.model.timeline import BaseClip, ImageClip

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

# ── Dimensions ────────────────────────────────────────────────────────────────
_HEADER_W = 130     # largeur colonne labels (gauche, fixe)
_RULER_H = 24       # hauteur de la règle temporelle
_TRACK_H = 60       # hauteur d'une piste
_MIN_CONTENT_W = 800

# ── Zoom ──────────────────────────────────────────────────────────────────────
_ZOOM_LEVELS = [1, 5, 10, 25, 50, 75, 100, 150, 200, 300, 400]
_DEFAULT_ZOOM_IDX = 6  # 100 px/s par défaut
_zoom_idx: int = _DEFAULT_ZOOM_IDX
_px_per_sec: int = _ZOOM_LEVELS[_DEFAULT_ZOOM_IDX]

# ── Couleurs ──────────────────────────────────────────────────────────────────
_COLOR_RULER_BG = (28, 28, 32, 255)
_COLOR_TICK = (120, 120, 130, 255)
_COLOR_TICK_LABEL = (170, 170, 180, 255)
_COLOR_CLIP_FILL = (50, 110, 170, 210)
_COLOR_CLIP_BORDER = (90, 150, 210, 255)
_COLOR_CLIP_TEXT = (220, 225, 235, 255)
_COLOR_PLAYHEAD = (210, 60, 60, 255)

# ── État ──────────────────────────────────────────────────────────────────────
_clips: list[BaseClip] = []
_playhead_sec: float = 0.0
_editor = None
_on_error = None
_gesture = None


def create() -> None:
    global _zoom_idx, _px_per_sec, _clips, _playhead_sec
    global _editor, _gesture
    _editor, _gesture = None, None
    _zoom_idx = _DEFAULT_ZOOM_IDX
    _px_per_sec = _ZOOM_LEVELS[_DEFAULT_ZOOM_IDX]
    _clips = []
    _playhead_sec = 0.0

    with dpg.item_handler_registry(tag=_HANDLER_TAG):
        dpg.add_item_resize_handler(callback=_on_resize)

    with dpg.child_window(tag=TAG, border=True):
        # ── Barre d'outils ────────────────────────────────────────────────────
        with dpg.group(horizontal=True, tag=_TOOLBAR_TAG):
            dpg.add_button(label="-", width=24, height=22, callback=_zoom_out)
            dpg.add_button(label="+", width=24, height=22, callback=_zoom_in)
            dpg.add_text("Glissez les clips / leurs bords. Pistes hautes = premier plan.")
        dpg.add_slider_float(tag=CURSOR, label="Position (s)", width=-120,
                             min_value=0, max_value=0, format="%.2f",
                             callback=lambda s, v: _editor.seek(v) if _editor else None)
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

    dpg.bind_item_handler_registry(TAG, _HANDLER_TAG)
    with dpg.item_handler_registry(tag="timeline_click_handler"):
        dpg.add_item_clicked_handler(button=dpg.mvMouseButton_Left, callback=_click)
    dpg.bind_item_handler_registry(_DRAWLIST_TAG, "timeline_click_handler")
    with dpg.handler_registry(tag="timeline_mouse_handlers"):
        dpg.add_mouse_drag_handler(button=dpg.mvMouseButton_Left, threshold=3, callback=_drag)
        dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Left, callback=_release)


def add_clip(clip: BaseClip) -> None:
    _clips.append(clip)
    _redraw()


def clear() -> None:
    _clips.clear()
    _redraw()


def set_playhead(seconds: float) -> None:
    global _playhead_sec
    _playhead_sec = seconds
    dpg.set_value(CURSOR, seconds)
    _redraw()


def bind(editor, on_error):
    global _editor, _on_error
    _editor, _on_error = editor, on_error
    refresh()


def refresh():
    global _clips
    if _editor is not None:
        _clips = list(_editor.project.timeline.clips)
        dpg.configure_item(CURSOR, max_value=_editor.project.timeline.duration)
    _redraw()


def _tracks():
    return list(range(max((c.track for c in _clips), default=0), -1, -1))


def _mouse():
    x, y = dpg.get_mouse_pos(local=False)
    ox, oy = dpg.get_item_rect_min(_DRAWLIST_TAG)
    return x - ox, y - oy


def _click():
    global _gesture
    if _editor is None:
        return
    x, y = _mouse()
    tracks = _tracks()
    row = int((y - _RULER_H) // _TRACK_H)
    if y < _RULER_H or not 0 <= row < len(tracks):
        _editor.seek(max(0, x / _px_per_sec))
        return
    for clip in reversed(_clips):
        if (clip.track == tracks[row]
                and clip.timeline_start <= x / _px_per_sec <= clip.timeline_end):
            _editor.select(clip.id)
            _editor.playback.pause()
            mode = "move"
            if abs(x - clip.timeline_start * _px_per_sec) <= 6:
                mode = "left"
            elif abs(x - clip.timeline_end * _px_per_sec) <= 6:
                mode = "right"
            _gesture = (replace(clip), x, tracks[0], mode)
            return
    _editor.seek(max(0, x / _px_per_sec))


def _drag():
    if _gesture is None or _editor is None:
        return
    clip, origin_x, highest, mode = _gesture
    x, y = _mouse()
    fps = _editor.project.timeline.fps
    delta = round((x - origin_x) / _px_per_sec * fps) / fps
    start = clip.timeline_start
    if mode == "move":
        start = max(0, round((start + delta) * fps) / fps)
        track = max(0, min(99, highest + 1, highest - int((y - _RULER_H) // _TRACK_H)))
        changes = {"timeline_start": start, "track": track}
    elif mode == "left":
        limit = start if isinstance(clip, ImageClip) else min(start, clip.source_start)
        delta = max(-limit, min(delta, clip.duration - 1 / fps))
        start += delta
        changes = {"timeline_start": start}
        if isinstance(clip, ImageClip):
            changes["display_duration"] = clip.duration - delta
        else:
            changes["source_start"] = clip.source_start + delta
    else:
        delta = max(1 / fps - clip.duration, delta)
        if isinstance(clip, ImageClip):
            changes = {"display_duration": clip.duration + delta}
        else:
            end = min(clip.media.duration or clip.source_end, clip.source_end + delta)
            changes = {"source_end": end}
    current = _editor.selected
    if current is None or all(getattr(current, k) == v for k, v in changes.items()):
        return
    try:
        _editor.update_clip(clip.id, position=start, **changes)
    except ValueError as exc:
        if _on_error:
            _on_error(str(exc))


def _release():
    global _gesture
    _gesture = None


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
    return _RULER_H + len(_tracks()) * _TRACK_H


def _content_width() -> int:
    if not _clips:
        return _MIN_CONTENT_W
    max_end = max(c.timeline_end for c in _clips)
    return max(_MIN_CONTENT_W, int(max_end * _px_per_sec) + 200)


def _on_resize() -> None:
    if dpg.does_item_exist(_DRAWLIST_TAG):
        dpg.configure_item(_DRAWLIST_TAG, width=_content_width(), height=_content_height())


# ── Dessin ────────────────────────────────────────────────────────────────────

def _redraw() -> None:
    if not dpg.does_item_exist(_DRAWLIST_TAG):
        return
    dpg.delete_item(_DRAWLIST_TAG, children_only=True)
    _update_headers()
    w = _content_width()
    dpg.configure_item(_DRAWLIST_TAG, width=w, height=_content_height())
    _draw_ruler(w)
    _draw_clips()
    _draw_playhead()


def _update_headers() -> None:
    if not dpg.does_item_exist(_HEADERS_TAG):
        return
    dpg.delete_item(_HEADERS_TAG, children_only=True)
    labels = dpg.add_drawlist(width=_HEADER_W - 20, height=_content_height(), parent=_HEADERS_TAG)
    for row, track in enumerate(_tracks()):
        dpg.draw_text((0, _RULER_H + row * _TRACK_H + _TRACK_H // 2 - 7),
                      f"Piste {track + 1}", size=13, parent=labels)
    dpg.set_y_scroll(_HEADERS_TAG, dpg.get_y_scroll(_SCROLL_TAG))


def _draw_ruler(total_w: int) -> None:
    dpg.draw_rectangle(
        (0, 0), (total_w, _RULER_H),
        fill=_COLOR_RULER_BG,
        color=(0, 0, 0, 0),
        parent=_DRAWLIST_TAG,
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
            parent=_DRAWLIST_TAG,
        )
        if is_major:
            dpg.draw_text(
                (x + 3, _RULER_H - tick_h - 13),
                _format_time(s),
                color=_COLOR_TICK_LABEL,
                size=11,
                parent=_DRAWLIST_TAG,
            )
        s += minor_step


def _draw_clips() -> None:
    clip_h = _TRACK_H - 8
    th_w = int(clip_h * THUMB_W / THUMB_H)

    tracks = _tracks()
    for clip in _clips:
        i = tracks.index(clip.track)
        clip_y = _RULER_H + i * _TRACK_H + 4
        x = int(clip.timeline_start * _px_per_sec)
        w = max(2, int(clip.duration * _px_per_sec))

        dpg.draw_rectangle(
            (x, clip_y), (x + w, clip_y + clip_h),
            fill=_COLOR_CLIP_FILL,
            color=((255, 190, 65, 255) if _editor and _editor.selected_id == clip.id
                   else _COLOR_CLIP_BORDER),
            thickness=2,
            parent=_DRAWLIST_TAG,
        )

        texture_tag = f"texture_{clip.media.id}"
        if dpg.does_item_exist(texture_tag) and w >= 8:
            img_w = min(th_w, w)
            dpg.draw_image(
                texture_tag,
                (x, clip_y),
                (x + img_w, clip_y + clip_h),
                parent=_DRAWLIST_TAG,
            )

        if w >= 40:
            dpg.draw_text(
                (x + 5, clip_y + clip_h // 2 - 6),
                clip.media.path.stem[:max(1, (w - 10) // 7)],
                color=_COLOR_CLIP_TEXT,
                size=12,
                parent=_DRAWLIST_TAG,
            )


def _draw_playhead() -> None:
    x = int(_playhead_sec * _px_per_sec)
    total_h = _content_height()
    dpg.draw_triangle(
        (x - 6, 0), (x + 6, 0), (x, 10),
        fill=_COLOR_PLAYHEAD,
        color=(0, 0, 0, 0),
        parent=_DRAWLIST_TAG,
    )
    dpg.draw_line(
        (x, 0), (x, total_h),
        color=_COLOR_PLAYHEAD,
        thickness=2,
        parent=_DRAWLIST_TAG,
    )


def _format_time(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    if m:
        return f"{m}:{s:02}"
    return f"{s}s"
