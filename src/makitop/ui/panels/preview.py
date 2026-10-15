"""Cadre de composition : sélection, déplacement, taille et recadrage à la souris."""

import cv2
import dearpygui.dearpygui as dpg
import numpy as np

from makitop.model.composition import FORMATS, drag_transform, fitted_bounds

TAG = "preview_panel"
VIDEO_TEXTURE_TAG = "video_texture"
VIDEO_IMAGE_TAG = "video_image"
TIME_TEXT_TAG = "preview_time"
FINAL_TIME_TEXT_TAG = "final_time"
CANVAS = "preview_canvas"
OVERLAY = "preview_selection"
PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 360

_editor = None
_on_error = None
_gesture = None
_size = (640, 360)
_available = (640, 360)
_time = 0.0


def bind(editor, on_error):
    global _editor, _on_error
    _editor, _on_error = editor, on_error
    refresh()


def _call(action):
    try:
        action()
    except (ValueError, KeyError, StopIteration) as exc:
        if _on_error:
            _on_error(str(exc))


def clear():
    update_frame(np.zeros((PREVIEW_HEIGHT, PREVIEW_WIDTH, 3), dtype=np.uint8))
    update_time(0)
    initFinalTime(0)


def create_video_texture():
    with dpg.texture_registry():
        dpg.add_dynamic_texture(
            width=PREVIEW_WIDTH, height=PREVIEW_HEIGHT,
            default_value=np.zeros(PREVIEW_WIDTH * PREVIEW_HEIGHT * 4, dtype=np.float32),
            tag=VIDEO_TEXTURE_TAG,
        )


def update_frame(frame):
    rgb = cv2.resize(frame, (PREVIEW_WIDTH, PREVIEW_HEIGHT)).astype(np.float32) / 255
    rgba = np.concatenate((rgb, np.ones((PREVIEW_HEIGHT, PREVIEW_WIDTH, 1))), axis=2)
    dpg.set_value(VIDEO_TEXTURE_TAG, rgba.astype(np.float32).ravel())


def format_time(seconds):
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def update_time(seconds):
    global _time
    _time = seconds
    dpg.set_value(TIME_TEXT_TAG, format_time(seconds))
    if dpg.does_item_exist(OVERLAY):
        _draw_selection()


def initFinalTime(seconds):
    dpg.set_value(FINAL_TIME_TEXT_TAG, format_time(seconds))


def create(on_play=None, on_pause=None, on_stop=None):
    global _editor, _gesture, _size, _available, _time
    _editor, _gesture, _time = None, None, 0
    _size, _available = (640, 360), (640, 360)
    with dpg.child_window(tag=TAG, border=True):
        with dpg.group(horizontal=True):
            dpg.add_text("Composition", tag="preview_mode")
            dpg.add_combo(list(FORMATS), default_value="16:9", width=85,
                          tag="composition_format", callback=_format_changed)
            dpg.add_checkbox(label="Recadrer", tag="composition_crop",
                             callback=lambda: _draw_selection())
        with dpg.group(horizontal=True):
            dpg.add_button(label="Voir le montage", tag="composition_show",
                           callback=lambda: _call(lambda: _editor.show_montage()))
            dpg.add_text("Glissez un média ici")
        with dpg.group(tag="composition_drop", payload_type="MAKITOP_MEDIA", drop_callback=_drop):
            dpg.add_drawlist(width=640, height=360, tag=CANVAS)
        dpg.draw_image(VIDEO_TEXTURE_TAG, (0, 0), _size, tag=VIDEO_IMAGE_TAG, parent=CANVAS)
        with dpg.draw_layer(tag=OVERLAY, parent=CANVAS):
            pass
        with dpg.group(horizontal=True):
            dpg.add_button(label="Play", callback=on_play)
            dpg.add_button(label="Pause", callback=on_pause)
            dpg.add_button(label="Stop", callback=on_stop)
            dpg.add_text("00:00", tag=TIME_TEXT_TAG)
            dpg.add_text("/")
            dpg.add_text("00:00", tag=FINAL_TIME_TEXT_TAG)
    with dpg.item_handler_registry(tag="composition_click_handler"):
        dpg.add_item_clicked_handler(button=dpg.mvMouseButton_Left, callback=_click)
    dpg.bind_item_handler_registry(CANVAS, "composition_click_handler")
    with dpg.handler_registry(tag="composition_mouse_handlers"):
        dpg.add_mouse_drag_handler(button=dpg.mvMouseButton_Left, threshold=0, callback=_drag)
        dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Left, callback=_release)


def resize(width, height):
    global _available, _size
    _available = (max(40, width - 20), max(40, height - 118))
    ratio = _editor.project.canvas_ratio if _editor else 16 / 9
    w = min(_available[0], _available[1] * ratio)
    _size = (max(1, round(w)), max(1, round(w / ratio)))
    dpg.configure_item(CANVAS, width=_size[0], height=_size[1])
    dpg.configure_item(VIDEO_IMAGE_TAG, pmax=_size)
    _draw_selection()


def refresh():
    if _editor is None:
        return
    dpg.set_value("composition_format", _editor.project.canvas_format)
    dpg.set_value("preview_mode", "Source" if _editor.source_mode else "Montage")
    initFinalTime(_editor.playback.duration)
    resize(_available[0] + 20, _available[1] + 118)


def _bounds(clip):
    return fitted_bounds(clip.transform, clip.media.width, clip.media.height,
                         _editor.project.canvas_ratio)


def _handles(bounds):
    x, y, w, h = bounds
    if dpg.get_value("composition_crop"):
        return {"left": (x, y + h / 2), "right": (x + w, y + h / 2),
                "top": (x + w / 2, y), "bottom": (x + w / 2, y + h)}
    return {"top_left": (x, y), "top_right": (x + w, y),
            "bottom_left": (x, y + h), "bottom_right": (x + w, y + h)}


def _draw_selection():
    dpg.delete_item(OVERLAY, children_only=True)
    dpg.draw_rectangle((0, 0), _size, color=(110, 115, 125, 255), parent=OVERLAY)
    if _editor is None or _editor.source_mode:
        return
    clip = _editor.selected
    if clip is None or not (clip.timeline_start <= _time < clip.timeline_end):
        return
    x, y, w, h = bounds = _bounds(clip)
    sw, sh = _size
    color = (245, 180, 60, 255) if dpg.get_value("composition_crop") else (80, 180, 255, 255)
    dpg.draw_rectangle((x * sw, y * sh), ((x + w) * sw, (y + h) * sh),
                       color=color, thickness=2, parent=OVERLAY)
    for hx, hy in _handles(bounds).values():
        dpg.draw_rectangle((hx * sw - 5, hy * sh - 5), (hx * sw + 5, hy * sh + 5),
                           fill=color, color=(255, 255, 255, 255), parent=OVERLAY)


def _mouse():
    mx, my = dpg.get_mouse_pos(local=False)
    x, y = dpg.get_item_rect_min(CANVAS)
    return (mx - x) / _size[0], (my - y) / _size[1]


def _click():
    global _gesture
    if _editor is None or _editor.source_mode:
        return
    point = _mouse()
    selected = _editor.selected
    handle = "move"
    if selected is not None and selected in _editor.project.timeline.clips_at(_time):
        for name, (x, y) in _handles(_bounds(selected)).items():
            if abs(point[0] - x) * _size[0] <= 8 and abs(point[1] - y) * _size[1] <= 8:
                handle = name
                break
    if handle == "move":
        selected = None
        for clip in reversed(_editor.project.timeline.clips_at(_time)):
            x, y, w, h = _bounds(clip)
            if x <= point[0] <= x + w and y <= point[1] <= y + h:
                selected = clip
                break
    _editor.select(selected.id if selected else None)
    if selected:
        _editor.playback.pause()
        _gesture = (selected.id, selected.transform, _bounds(selected), point,
                    "crop" if dpg.get_value("composition_crop") else "resize", handle)


def _drag():
    if _gesture is None or _editor is None:
        return
    clip_id, original, bounds, origin, mode, handle = _gesture
    point = _mouse()
    def apply():
        transform = drag_transform(original, bounds, mode, handle,
                                   point[0] - origin[0], point[1] - origin[1],
                                   _editor.project.canvas_ratio)
        if _editor.selected is not None and transform != _editor.selected.transform:
            _editor.update_clip(clip_id, transform=transform)
    _call(apply)


def _release():
    global _gesture
    _gesture = None


def _drop(sender, app_data):
    if _editor is not None:
        _call(lambda: _editor.add_media(next(m for m in _editor.project.media if m.id == app_data)))


def _format_changed(sender, value):
    if _editor is not None:
        _call(lambda: _editor.set_format(value))