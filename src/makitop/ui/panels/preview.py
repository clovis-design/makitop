"""Cadre de composition : sélection, déplacement, taille et recadrage à la souris."""

import math
from dataclasses import replace

import cv2
import dearpygui.dearpygui as dpg
import numpy as np

from makitop.model.composition import FORMATS, drag_transform, fitted_bounds, rotate_point
from makitop.model.media import MediaKind
from makitop.model.timeline import TextClip
from makitop.ui.panels import transport_icons

TAG = "preview_panel"
VIDEO_TEXTURE_TAG = "video_texture"
VIDEO_IMAGE_TAG = "video_image"
TIME_TEXT_TAG = "preview_time"
FINAL_TIME_TEXT_TAG = "final_time"
CANVAS = "preview_canvas"
OVERLAY = "preview_selection"
PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 360
TEXTURES = "preview_textures"
FPS_CHOICES = ["24", "25", "30", "48", "50", "60", "90", "120"]
PREVIEW_QUALITIES = {"Fluide (360p)": 360, "HD (720p)": 720, "Full HD (1080p)": 1080}
TRANSPORT_SPACER = "transport_spacer"
TRANSPORT_THEME = "transport_theme"
PLAY_BUTTON = "transport_play"
# Largeur approximative des boutons + temps, pour centrer la barre.
TRANSPORT_WIDTH = 250

_editor = None
_playback = None
_shown_playing = False
_on_error = None
_gesture = None
_size = (640, 360)
_available = (640, 360)
_time = 0.0
_texture = VIDEO_TEXTURE_TAG
_pixels = None
_rgba8 = None
_selection_key = None


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
    global _texture, _pixels, _rgba8
    _texture = VIDEO_TEXTURE_TAG
    _pixels = np.zeros((PREVIEW_HEIGHT, PREVIEW_WIDTH, 4), dtype=np.float32)
    _pixels[:, :, 3] = 1
    _rgba8 = np.empty((PREVIEW_HEIGHT, PREVIEW_WIDTH, 4), dtype=np.uint8)
    with dpg.texture_registry(tag=TEXTURES):
        dpg.add_raw_texture(
            width=PREVIEW_WIDTH, height=PREVIEW_HEIGHT,
            default_value=_pixels.ravel(), format=dpg.mvFormat_Float_rgba,
            tag=VIDEO_TEXTURE_TAG,
        )


def update_frame(frame):
    global _texture, _pixels, _rgba8
    height, width = frame.shape[:2]
    if _pixels.shape[:2] != (height, width):
        pixels = np.empty((height, width, 4), dtype=np.float32)
        pixels[:, :, 3] = 1
        texture = dpg.add_raw_texture(
            width, height, pixels.ravel(), format=dpg.mvFormat_Float_rgba, parent=TEXTURES,
        )
        if dpg.does_item_exist(VIDEO_IMAGE_TAG):
            dpg.configure_item(VIDEO_IMAGE_TAG, texture_tag=texture)
        dpg.delete_item(_texture)
        _texture, _pixels = texture, pixels
        _rgba8 = np.empty((height, width, 4), dtype=np.uint8)
    # Buffer float32 réutilisé directement par la texture : ni redimensionnement
    # à 640×360, ni tableau float64 intermédiaire, ni copie Python par pixel.
    cv2.cvtColor(frame, cv2.COLOR_RGB2RGBA, dst=_rgba8)
    np.multiply(_rgba8, np.float32(1 / 255), out=_pixels)


def format_time(seconds):
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def update_time(seconds):
    global _time
    _time = seconds
    dpg.set_value(TIME_TEXT_TAG, format_time(seconds))
    _sync_play_icon()
    if dpg.does_item_exist(OVERLAY):
        _draw_selection()


def _sync_play_icon():
    """Bascule ▶/⏸ seulement quand l'état de lecture change (fin de timeline, clic…)."""
    global _shown_playing
    playing = bool(_playback is not None and _playback.is_playing())
    if playing != _shown_playing and dpg.does_item_exist(PLAY_BUTTON):
        _shown_playing = playing
        dpg.configure_item(PLAY_BUTTON, texture_tag=transport_icons.texture_tag(
            "pause" if playing else "play"))


def initFinalTime(seconds):
    dpg.set_value(FINAL_TIME_TEXT_TAG, format_time(seconds))


def _go_start():
    if _playback is not None:
        _call(lambda: _playback.seek(0))


def _stop():
    if _playback is not None:
        _call(_playback.stop)


def _toggle_play():
    if _playback is not None:
        _call(_playback.pause if _playback.is_playing() else _playback.play)
        _sync_play_icon()


def _go_end():
    if _playback is not None:
        _call(lambda: _playback.seek(_playback.duration))


def _transport_theme():
    if dpg.does_alias_exist(TRANSPORT_THEME):
        return
    with dpg.theme(tag=TRANSPORT_THEME), dpg.theme_component(dpg.mvImageButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (60, 66, 95))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (41, 74, 122))
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
        dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 6, 4)


def _transport_button(name, tag, tooltip, callback):
    dpg.add_image_button(transport_icons.texture_tag(name), tag=tag, callback=callback,
                         width=transport_icons.ICON_SIZE, height=transport_icons.ICON_SIZE)
    with dpg.tooltip(tag):
        dpg.add_text(tooltip)


def create(playback=None):
    global _editor, _playback, _shown_playing, _gesture, _size, _available, _time
    _editor, _gesture, _time = None, None, 0
    _playback, _shown_playing = playback, False
    _size, _available = (640, 360), (640, 360)
    transport_icons.load_textures()
    _transport_theme()
    with dpg.child_window(tag=TAG, border=True):
        with dpg.group(horizontal=True):
            dpg.add_combo(FPS_CHOICES, default_value="60", width=65,
                          tag="composition_fps", callback=_fps_changed)
            dpg.add_text("fps")
            dpg.add_combo(list(PREVIEW_QUALITIES), default_value="HD (720p)", width=145,
                          tag="preview_quality", callback=_quality_changed)
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
        dpg.draw_image(_texture, (0, 0), _size, tag=VIDEO_IMAGE_TAG, parent=CANVAS)
        with dpg.draw_layer(tag=OVERLAY, parent=CANVAS):
            pass
        with dpg.group(horizontal=True) as transport:
            dpg.bind_item_theme(transport, TRANSPORT_THEME)
            dpg.add_spacer(width=0, tag=TRANSPORT_SPACER)
            _transport_button("start", "transport_start", "Aller au début", _go_start)
            _transport_button("stop", "transport_stop", "Arrêter", _stop)
            _transport_button("play", PLAY_BUTTON, "Lecture / Pause", _toggle_play)
            _transport_button("end", "transport_end", "Aller à la fin", _go_end)
            dpg.add_spacer(width=8)
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
    _available = (max(40, width - 20), max(40, height - 145))
    ratio = _editor.project.canvas_ratio if _editor else 16 / 9
    w = min(_available[0], _available[1] * ratio)
    _size = (max(1, round(w)), max(1, round(w / ratio)))
    dpg.configure_item(CANVAS, width=_size[0], height=_size[1])
    dpg.configure_item(VIDEO_IMAGE_TAG, pmax=_size)
    dpg.configure_item(TRANSPORT_SPACER, width=max(0, (_available[0] - TRANSPORT_WIDTH) // 2))
    _draw_selection()


def refresh():
    if _editor is None:
        return
    dpg.set_value("composition_format", _editor.project.canvas_format)
    playing_project = _editor.playback.project or _editor.project
    dpg.set_value("composition_fps", str(playing_project.timeline.fps))
    dpg.configure_item("composition_fps", enabled=not _editor.source_mode)
    dpg.set_value("preview_mode", "Source" if _editor.source_mode else "Montage")
    initFinalTime(_editor.playback.duration)
    resize(_available[0] + 20, _available[1] + 145)


def _bounds(clip):
    transform = clip.transform_at(_time - clip.timeline_start)
    if isinstance(clip, TextClip):
        return transform.x, transform.y, transform.width, transform.height
    return fitted_bounds(transform, clip.media.width, clip.media.height,
                         _editor.project.canvas_ratio)


def _crop_enabled(clip):
    return not isinstance(clip, TextClip) and dpg.get_value("composition_crop")


def _bounds_center(bounds):
    x, y, w, h = bounds
    return x + w / 2, y + h / 2


def _rotation(clip):
    return clip.transform.rotation if clip is not None and not isinstance(clip, TextClip) else 0.0


def _can_rotate(clip):
    return not isinstance(clip, TextClip) and clip.media.kind != MediaKind.AUDIO


def _rotate_point(point, center, angle):
    return rotate_point(point, center, angle, _size[0] / _size[1])


def _handles(bounds, crop, rotation=0):
    x, y, w, h = bounds
    if crop:
        points = {"left": (x, y + h / 2), "right": (x + w, y + h / 2),
                  "top": (x + w / 2, y), "bottom": (x + w / 2, y + h)}
    else:
        points = {"top_left": (x, y), "top_right": (x + w, y),
                  "bottom_right": (x + w, y + h), "bottom_left": (x, y + h)}
    center = _bounds_center(bounds)
    return {name: _rotate_point(point, center, rotation) for name, point in points.items()}


def _rotation_handle(bounds, rotation):
    """Positionne la poignée à l'extérieur si possible, sinon à l'intérieur du cadre."""
    x, y, w, h = bounds
    sw, sh = _size
    center = _bounds_center(bounds)
    edges = ((x + w / 2, y, 0, -1), (x + w / 2, y + h, 0, 1),
             (x + w, y + h / 2, 1, 0), (x, y + h / 2, -1, 0))
    for distance in (22, -22):
        for ax, ay, dx, dy in edges:
            head = _rotate_point((ax + dx * distance / sw, ay + dy * distance / sh),
                                 center, rotation)
            radius = math.hypot((head[0] - center[0]) * sw, (head[1] - center[1]) * sh)
            if 10 <= head[0] * sw <= sw - 10 and 10 <= head[1] * sh <= sh - 10 and radius >= 12:
                return _rotate_point((ax, ay), center, rotation), head
    return None


def _draw_selection():
    global _selection_key
    clip = _editor.selected if _editor is not None and not _editor.source_mode else None
    if clip is not None and not (clip.timeline_start <= _time < clip.timeline_end):
        clip = None
    bounds = _bounds(clip) if clip is not None else None
    crop = _crop_enabled(clip)
    rotation = _rotation(clip)
    can_rotate = clip is not None and _can_rotate(clip) and not crop
    key = (_size, bounds, crop, rotation, can_rotate)
    if key == _selection_key:
        return
    _selection_key = key
    dpg.delete_item(OVERLAY, children_only=True)
    dpg.draw_rectangle((0, 0), _size, color=(110, 115, 125, 255), parent=OVERLAY)
    if _editor is None or _editor.source_mode:
        return
    if clip is None:
        return
    sw, sh = _size
    color = (245, 180, 60, 255) if crop else (80, 180, 255, 255)
    corners = _handles(bounds, False, rotation).values()
    dpg.draw_polygon([(px * sw, py * sh) for px, py in corners],
                     color=color, thickness=2, parent=OVERLAY)
    for hx, hy in _handles(bounds, crop, rotation).values():
        dpg.draw_rectangle((hx * sw - 5, hy * sh - 5), (hx * sw + 5, hy * sh + 5),
                           fill=color, color=(255, 255, 255, 255), parent=OVERLAY)
    handle = _rotation_handle(bounds, rotation) if can_rotate else None
    if handle is not None:
        (ax, ay), (hx, hy) = handle
        dpg.draw_line((ax * sw, ay * sh), (hx * sw, hy * sh), color=color, parent=OVERLAY)
        dpg.draw_circle((hx * sw, hy * sh), 6, fill=color, color=(255, 255, 255, 255),
                        parent=OVERLAY, tag="preview_rotation_handle")


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
        bounds = _bounds(selected)
        crop = _crop_enabled(selected)
        rotation = _rotation(selected)
        handles = _handles(bounds, crop, rotation)
        rotation_handle = (
            _rotation_handle(bounds, rotation) if _can_rotate(selected) and not crop else None
        )
        if rotation_handle is not None:
            handles = {"rotate": rotation_handle[1], **handles}
        for name, (x, y) in handles.items():
            if math.hypot((point[0] - x) * _size[0], (point[1] - y) * _size[1]) <= 9:
                handle = name
                break
    if handle == "move":
        selected = None
        for clip in reversed(_editor.project.timeline.clips_at(_time)):
            bounds = _bounds(clip)
            x, y, w, h = bounds
            px, py = _rotate_point(point, _bounds_center(bounds), -_rotation(clip))
            if x <= px <= x + w and y <= py <= y + h:
                selected = clip
                break
    _editor.select(selected.id if selected else None)
    if selected:
        _editor.playback.pause()
        time = _time - selected.timeline_start
        text_box = selected.unzoomed_transform_at(time) if isinstance(selected, TextClip) else None
        _gesture = (selected.id, selected.transform_at(time), _bounds(selected), point,
                    "crop" if _crop_enabled(selected) else "resize", handle, text_box)


def _drag():
    if _gesture is None or _editor is None:
        return
    clip_id, original, bounds, origin, mode, handle, text_box = _gesture
    point = _mouse()

    def apply():
        clip = _editor.selected
        if clip is None or clip.id != clip_id:
            return
        time = _time - clip.timeline_start
        if handle == "rotate":
            cx, cy = _bounds_center(bounds)
            sw, sh = _size
            dx, dy = (point[0] - cx) * sw, (point[1] - cy) * sh
            if math.hypot(dx, dy) > 5:
                initial = math.atan2((origin[1] - cy) * sh, (origin[0] - cx) * sw)
                angle = original.rotation + math.degrees(math.atan2(dy, dx) - initial)
                _editor.set_clip_orientation(rotation=round(angle, 1))
            return
        delta = point[0] - origin[0], point[1] - origin[1]
        rotated_resize = bool(original.rotation and handle != "move")
        if rotated_resize:
            delta = _rotate_point(delta, (0, 0), -original.rotation)
        mirrored_crop = mode == "crop" and (original.flip_horizontal or original.flip_vertical)
        base = _swap_mirrored_crop(original) if mirrored_crop else original
        transform = drag_transform(base, bounds, mode, handle, *delta,
                                   _editor.project.canvas_ratio)
        if mirrored_crop:
            transform = _swap_mirrored_crop(transform)
        if rotated_resize:
            # Ancrer le coin opposé dans le repère tourné, comme dans le cadre droit.
            center = _bounds_center((transform.x, transform.y, transform.width, transform.height))
            cx, cy = _rotate_point(center, _bounds_center(bounds), original.rotation)
            transform = replace(transform, x=transform.x + cx - center[0],
                                y=transform.y + cy - center[1])
        if text_box is not None and handle == "move":
            transform = replace(text_box,
                                x=max(-8, min(8, text_box.x + transform.x - original.x)),
                                y=max(-8, min(8, text_box.y + transform.y - original.y)))
        elif text_box is not None and any(key.property == "zoom" for key in clip.keyframes):
            if abs(transform.width - clip.transform_at(time).width) > 1e-9:
                _editor.set_animated_value("zoom", transform.width)
            return
        current = (clip.unzoomed_transform_at(time) if text_box is not None
                   else clip.transform_at(time))
        if transform != current:
            _editor.update_clip(clip_id, transform=transform)
    _call(apply)


def _swap_mirrored_crop(transform):
    if transform.flip_horizontal:
        transform = replace(transform, crop_left=transform.crop_right,
                            crop_right=transform.crop_left)
    if transform.flip_vertical:
        transform = replace(transform, crop_top=transform.crop_bottom,
                            crop_bottom=transform.crop_top)
    return transform


def _release():
    global _gesture
    _gesture = None


def _drop(sender, app_data):
    if _editor is not None:
        _call(lambda: _editor.add_media(next(m for m in _editor.project.media if m.id == app_data)))


def _format_changed(sender, value):
    if _editor is not None:
        _call(lambda: _editor.set_format(value))


def _fps_changed(sender, value):
    if _editor is not None:
        _call(lambda: _editor.set_fps(int(value)))


def _quality_changed(sender, value):
    if _editor is not None:
        _call(lambda: _editor.playback.set_preview_height(PREVIEW_QUALITIES[value]))
