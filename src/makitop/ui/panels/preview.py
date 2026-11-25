"""Viewer (inspiré de DaVinci Resolve) : en-tête de réglages, image centrée sur fond sombre,
barre de progression et barre de transport avec timecode.

Le cadre de composition gère la sélection, le déplacement, la taille et le recadrage
à la souris.
"""

import math
from dataclasses import replace

import cv2
import dearpygui.dearpygui as dpg
import numpy as np

from makitop.model.composition import FORMATS, drag_transform, fitted_bounds, rotate_point
from makitop.model.media import MediaKind
from makitop.model.timeline import TextClip
from makitop.ui.assets.style import COLORS
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
DROP_HINT = "Glissez un média ici"

HEADER = "preview_header"
HEADER_RIGHT = "preview_header_right"
VIEWER = "preview_viewer"
VIEWER_PAD_X = "preview_viewer_pad_x"
VIEWER_PAD_Y = "preview_viewer_pad_y"
SCRUBBER = "preview_scrubber"
SCRUB_TRACK = "preview_scrub_track"
SCRUB_FILL = "preview_scrub_fill"
SCRUB_HEAD = "preview_scrub_head"
TRANSPORT = "preview_transport"
TRANSPORT_BUTTONS = "preview_transport_buttons"
PLAY_BUTTON = "transport_play"
FULLSCREEN_BUTTON = "transport_fullscreen"
FULLSCREEN_HINT = "transport_fullscreen_hint"

PANEL_THEME = "preview_theme"
BAR_THEME = "preview_bar_theme"
VIEWER_THEME = "preview_viewer_theme"
TRANSPORT_THEME = "transport_theme"
PLAY_THEME = "transport_play_theme"

HEADER_H = 32
SCRUB_H = 10
TRANSPORT_H = 38
VIEWER_MARGIN = 12
BAR_PAD = (8, 5)
ITEM_SPACING = 6
QUALITY_W = 145
FPS_W = 60
BUTTON_PAD = (6, 4)
# Largeur des 4 boutons de transport (icône + marges) et de leurs espacements.
BUTTONS_W = 4 * (transport_icons.ICON_SIZE + 2 * BUTTON_PAD[0]) + 3 * ITEM_SPACING
BUTTONS_H = transport_icons.ICON_SIZE + 2 * BUTTON_PAD[1]
BUTTON_W = transport_icons.ICON_SIZE + 2 * BUTTON_PAD[0]
# Ordonnées dans la barre de transport, pour centrer verticalement chaque élément.
BUTTONS_Y = (TRANSPORT_H - BUTTONS_H) // 2
TIMECODE_Y = (TRANSPORT_H - 22) // 2
TOTAL_Y = (TRANSPORT_H - 18) // 2

_editor = None
_playback = None
_shown_playing = False
_on_error = None
_gesture = None
_scrubbing = False
_fullscreen = False
_on_toggle_fullscreen = None
_panel = (PREVIEW_WIDTH + 2 * VIEWER_MARGIN,
          PREVIEW_HEIGHT + 2 * VIEWER_MARGIN + HEADER_H + SCRUB_H + TRANSPORT_H)
_size = (PREVIEW_WIDTH, PREVIEW_HEIGHT)
_available = (PREVIEW_WIDTH, PREVIEW_HEIGHT)
_time = 0.0
_fps = 30
_shown_time = None
_scrub_px = None
_texture = VIDEO_TEXTURE_TAG
_pixels = None
_rgba8 = None
_selection_key = None
_on_export = None


def bind(editor, on_error):
    global _editor, _on_error
    _editor, _on_error = editor, on_error
    refresh()


def bind_export(fn) -> None:
    global _on_export
    _on_export = fn


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


def format_time(seconds, fps=30):
    """Timecode HH:MM:SS:FF, comme dans DaVinci Resolve."""
    fps = max(1, int(fps))
    frames = int(max(0.0, seconds) * fps + 1e-6)
    total, ff = divmod(frames, fps)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{ff:02d}"


def update_time(seconds):
    global _time, _shown_time
    _time = seconds
    text = format_time(seconds, _fps)
    if text != _shown_time:
        _shown_time = text
        dpg.set_value(TIME_TEXT_TAG, text)
    _sync_play_icon()
    _sync_scrubber()
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
    dpg.set_value(FINAL_TIME_TEXT_TAG, format_time(seconds, _fps))


def _duration():
    return _playback.duration if _playback is not None else 0


def _sync_scrubber():
    """Avance la partie lue de la barre de progression, au pixel près."""
    global _scrub_px
    if not dpg.does_item_exist(SCRUB_FILL):
        return
    width = _panel[0]
    duration = _duration()
    ratio = min(1.0, max(0.0, _time / duration)) if duration > 0 else 0.0
    px = round(ratio * width)
    if px == _scrub_px:
        return
    _scrub_px = px
    dpg.configure_item(SCRUB_FILL, pmax=(px, SCRUB_H - 2))
    dpg.configure_item(SCRUB_HEAD, pmin=(max(0, px - 1), 0), pmax=(max(2, px + 1), SCRUB_H))


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


# --- Construction ---------------------------------------------------------------

def _themes():
    if dpg.does_alias_exist(PANEL_THEME):
        return
    with dpg.theme(tag=PANEL_THEME):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, ITEM_SPACING, 0)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 6, 3)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, COLORS["field_bg"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, COLORS["field_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, COLORS["field_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_CheckMark, COLORS["accent_active"])
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["accent"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLORS["accent_active"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, COLORS["accent_active"])
            dpg.add_theme_color(dpg.mvThemeCol_Header, COLORS["accent"])
            dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, COLORS["section_hover"])
        # Flèche des listes déroulantes : discrète, l'accent n'apparaît qu'au survol.
        with dpg.theme_component(dpg.mvCombo):
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["field_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLORS["accent"])
    with dpg.theme(tag=BAR_THEME), dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["section_header"])
        dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, *BAR_PAD)
        dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, ITEM_SPACING, 4)
    with dpg.theme(tag=VIEWER_THEME), dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["viewer_bg"])
        dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 0, 0)
    with dpg.theme(tag=TRANSPORT_THEME), dpg.theme_component(dpg.mvImageButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLORS["section_hover"])
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, COLORS["accent"])
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
        dpg.add_theme_style(dpg.mvStyleVar_FramePadding, *BUTTON_PAD)
    with dpg.theme(tag=PLAY_THEME), dpg.theme_component(dpg.mvImageButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["accent"])
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLORS["accent_active"])
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, COLORS["accent_active"])
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
        dpg.add_theme_style(dpg.mvStyleVar_FramePadding, *BUTTON_PAD)


def _transport_button(name, tag, tooltip, callback):
    dpg.add_image_button(transport_icons.texture_tag(name), tag=tag, callback=callback,
                         width=transport_icons.ICON_SIZE, height=transport_icons.ICON_SIZE)
    with dpg.tooltip(tag):
        dpg.add_text(tooltip)


def _header():
    with dpg.child_window(tag=HEADER, height=HEADER_H, border=False, no_scrollbar=True,
                          always_use_window_padding=True):
        with dpg.group(horizontal=True):
            dpg.add_text("MONTAGE", tag="preview_mode", color=COLORS["accent_active"])
            dpg.add_button(label="Voir le montage", tag="composition_show", show=False,
                           callback=lambda: _call(lambda: _editor.show_montage()))
            dpg.add_spacer(width=4)
            dpg.add_combo(list(FORMATS), default_value="16:9", width=80,
                          tag="composition_format", callback=_format_changed)
            with dpg.tooltip("composition_format"):
                dpg.add_text("Format de la composition")
            dpg.add_checkbox(label="Recadrer", tag="composition_crop",
                             callback=lambda: _draw_selection())
        with dpg.group(horizontal=True, tag=HEADER_RIGHT, pos=(0, BAR_PAD[1])):
            dpg.add_combo(list(PREVIEW_QUALITIES), default_value="HD (720p)", width=QUALITY_W,
                          tag="preview_quality", callback=_quality_changed)
            with dpg.tooltip("preview_quality"):
                dpg.add_text("Qualité de la prévisualisation")
            dpg.add_combo(FPS_CHOICES, default_value="60", width=FPS_W,
                          tag="composition_fps", callback=_fps_changed)
            dpg.add_text("ips", color=COLORS["label_muted"])
            dpg.add_button(label="Exporter", tag="preview_export_btn",
                           callback=lambda: _on_export() if _on_export else None)
            with dpg.tooltip("preview_export_btn"):
                dpg.add_text("Exporter la vidéo")
    dpg.bind_item_theme(HEADER, BAR_THEME)


def _viewer():
    with dpg.child_window(tag=VIEWER, height=PREVIEW_HEIGHT, border=False, no_scrollbar=True):
        dpg.add_spacer(height=VIEWER_MARGIN, tag=VIEWER_PAD_Y)
        with dpg.group(horizontal=True, horizontal_spacing=0):
            dpg.add_spacer(width=VIEWER_MARGIN, tag=VIEWER_PAD_X)
            with dpg.group(tag="composition_drop", payload_type="MAKITOP_MEDIA",
                           drop_callback=_drop):
                dpg.add_drawlist(width=PREVIEW_WIDTH, height=PREVIEW_HEIGHT, tag=CANVAS)
    dpg.bind_item_theme(VIEWER, VIEWER_THEME)
    dpg.draw_image(_texture, (0, 0), _size, tag=VIDEO_IMAGE_TAG, parent=CANVAS)
    with dpg.draw_layer(tag=OVERLAY, parent=CANVAS):
        pass


def _scrubber():
    with dpg.drawlist(width=_panel[0], height=SCRUB_H, tag=SCRUBBER):
        dpg.draw_rectangle((0, 2), (_panel[0], SCRUB_H - 2), fill=COLORS["field_bg"],
                           color=COLORS["field_bg"], tag=SCRUB_TRACK)
        dpg.draw_rectangle((0, 2), (0, SCRUB_H - 2), fill=COLORS["accent"],
                           color=COLORS["accent"], tag=SCRUB_FILL)
        dpg.draw_rectangle((0, 0), (2, SCRUB_H), fill=COLORS["timecode"],
                           color=COLORS["timecode"], tag=SCRUB_HEAD)


def _transport():
    with dpg.child_window(tag=TRANSPORT, height=TRANSPORT_H, border=False, no_scrollbar=True,
                          always_use_window_padding=True):
        dpg.add_text("00:00:00:00", tag=TIME_TEXT_TAG, color=COLORS["timecode"],
                     pos=(BAR_PAD[0] + 2, TIMECODE_Y))
        if dpg.does_alias_exist("timecode_font"):
            dpg.bind_item_font(TIME_TEXT_TAG, "timecode_font")
        with dpg.group(horizontal=True, tag=TRANSPORT_BUTTONS,
                       pos=(0, BUTTONS_Y)):
            _transport_button("start", "transport_start", "Aller au début", _go_start)
            _transport_button("stop", "transport_stop", "Arrêter", _stop)
            _transport_button("play", PLAY_BUTTON, "Lecture / Pause", _toggle_play)
            _transport_button("end", "transport_end", "Aller à la fin", _go_end)
        dpg.bind_item_theme(TRANSPORT_BUTTONS, TRANSPORT_THEME)
        dpg.bind_item_theme(PLAY_BUTTON, PLAY_THEME)
        dpg.add_text("00:00:00:00", tag=FINAL_TIME_TEXT_TAG, color=COLORS["label_muted"],
                     pos=(0, TOTAL_Y))
        with dpg.tooltip(FINAL_TIME_TEXT_TAG):
            dpg.add_text("Durée totale")
        dpg.add_image_button(transport_icons.texture_tag("fullscreen"), tag=FULLSCREEN_BUTTON,
                             width=transport_icons.ICON_SIZE, height=transport_icons.ICON_SIZE,
                             pos=(0, BUTTONS_Y), callback=_toggle_fullscreen)
        with dpg.tooltip(FULLSCREEN_BUTTON):
            dpg.add_text("Plein écran (F)", tag=FULLSCREEN_HINT)
        dpg.bind_item_theme(FULLSCREEN_BUTTON, TRANSPORT_THEME)
    dpg.bind_item_theme(TRANSPORT, BAR_THEME)


def _toggle_fullscreen():
    if _on_toggle_fullscreen is not None:
        _on_toggle_fullscreen()


def set_fullscreen(on):
    """Viewer seul : sans en-tête ni marge, icône et infobulle « quitter »."""
    global _fullscreen
    _fullscreen = bool(on)
    dpg.configure_item(HEADER, show=not _fullscreen)
    dpg.configure_item(FULLSCREEN_BUTTON, texture_tag=transport_icons.texture_tag(
        "exit_fullscreen" if _fullscreen else "fullscreen"))
    dpg.set_value(FULLSCREEN_HINT, "Quitter le plein écran (F / Échap)" if _fullscreen
                  else "Plein écran (F)")
    _draw_selection()


def is_fullscreen():
    return _fullscreen


def create(playback=None, on_toggle_fullscreen=None):
    global _editor, _playback, _shown_playing, _gesture, _scrubbing, _size, _available
    global _time, _fps, _shown_time, _scrub_px, _selection_key
    global _fullscreen, _on_toggle_fullscreen
    _fullscreen, _on_toggle_fullscreen = False, on_toggle_fullscreen
    _editor, _gesture, _scrubbing, _time = None, None, False, 0
    _playback, _shown_playing = playback, False
    _fps, _shown_time, _scrub_px, _selection_key = 30, None, None, None
    _size, _available = (PREVIEW_WIDTH, PREVIEW_HEIGHT), (PREVIEW_WIDTH, PREVIEW_HEIGHT)
    transport_icons.load_textures()
    _themes()
    with dpg.child_window(tag=TAG, border=False, no_scrollbar=True):
        _header()
        _viewer()
        _scrubber()
        _transport()
    dpg.bind_item_theme(TAG, PANEL_THEME)
    with dpg.item_handler_registry(tag="composition_click_handler"):
        dpg.add_item_clicked_handler(button=dpg.mvMouseButton_Left, callback=_click)
    dpg.bind_item_handler_registry(CANVAS, "composition_click_handler")
    with dpg.item_handler_registry(tag="scrubber_click_handler"):
        dpg.add_item_clicked_handler(button=dpg.mvMouseButton_Left, callback=_scrub_click)
    dpg.bind_item_handler_registry(SCRUBBER, "scrubber_click_handler")
    with dpg.handler_registry(tag="composition_mouse_handlers"):
        dpg.add_mouse_drag_handler(button=dpg.mvMouseButton_Left, threshold=0, callback=_drag)
        dpg.add_mouse_release_handler(button=dpg.mvMouseButton_Left, callback=_release)


def _text_width(text, char_width=8.5):
    """Largeur d'un texte ; estimation tant que la police n'a pas encore été rendue."""
    try:
        size = dpg.get_text_size(text)
    except Exception:
        size = None
    return size[0] if size and size[0] > 0 else len(text) * char_width


def resize(width, height):
    global _panel, _available, _size, _scrub_px
    _panel = (max(80, int(width)), max(80, int(height)))
    width, height = _panel
    header_h, margin = (0, 0) if _fullscreen else (HEADER_H, VIEWER_MARGIN)
    viewer_h = max(40, height - header_h - SCRUB_H - TRANSPORT_H)
    _available = (max(40, width - 2 * margin), max(40, viewer_h - 2 * margin))
    ratio = _editor.project.canvas_ratio if _editor else 16 / 9
    w = min(_available[0], _available[1] * ratio)
    _size = (max(1, round(w)), max(1, round(w / ratio)))
    dpg.configure_item(VIEWER, width=width, height=viewer_h)
    dpg.configure_item(VIEWER_PAD_X, width=max(0, (width - _size[0]) // 2))
    dpg.configure_item(VIEWER_PAD_Y, height=max(0, (viewer_h - _size[1]) // 2))
    dpg.configure_item(CANVAS, width=_size[0], height=_size[1])
    dpg.configure_item(VIDEO_IMAGE_TAG, pmax=_size)
    # En-tête : qualité + fps alignés à droite.
    right_w = QUALITY_W + FPS_W + 3 * ITEM_SPACING + _text_width("ips") + _text_width("Exporter") + 16
    dpg.configure_item(HEADER_RIGHT, pos=(max(0, int(width - BAR_PAD[0] - right_w)),
                                          BAR_PAD[1]))
    # Barre de progression sur toute la largeur.
    dpg.configure_item(SCRUBBER, width=width)
    dpg.configure_item(SCRUB_TRACK, pmax=(width, SCRUB_H - 2))
    _scrub_px = None
    _sync_scrubber()
    # Transport : boutons centrés ; à droite, la durée totale puis le bouton plein écran.
    dpg.configure_item(TRANSPORT_BUTTONS, pos=(max(0, (width - BUTTONS_W) // 2), BUTTONS_Y))
    fullscreen_x = max(0, width - BAR_PAD[0] - BUTTON_W)
    dpg.configure_item(FULLSCREEN_BUTTON, pos=(fullscreen_x, BUTTONS_Y))
    total_w = _text_width(dpg.get_value(FINAL_TIME_TEXT_TAG) or "00:00:00:00")
    dpg.configure_item(FINAL_TIME_TEXT_TAG,
                       pos=(max(0, int(fullscreen_x - 2 * ITEM_SPACING - total_w)), TOTAL_Y))
    _draw_selection()


def refresh():
    global _fps, _shown_time
    if _editor is None:
        return
    dpg.set_value("composition_format", _editor.project.canvas_format)
    playing_project = _editor.playback.project or _editor.project
    _fps = playing_project.timeline.fps
    _shown_time = None
    dpg.set_value("composition_fps", str(_fps))
    dpg.configure_item("composition_fps", enabled=not _editor.source_mode)
    dpg.set_value("preview_mode", "SOURCE" if _editor.source_mode else "MONTAGE")
    dpg.configure_item("composition_show", show=_editor.source_mode)
    initFinalTime(_editor.playback.duration)
    resize(*_panel)


# --- Barre de progression -------------------------------------------------------

def _mouse_scrub():
    """Position de la souris sur la barre de progression, entre 0 et 1."""
    mx, _ = dpg.get_mouse_pos(local=False)
    x, _ = dpg.get_item_rect_min(SCRUBBER)
    return min(1.0, max(0.0, (mx - x) / max(1, _panel[0])))


def _seek_to_mouse():
    if _playback is not None and _duration() > 0:
        ratio = _mouse_scrub()
        _call(lambda: _playback.seek(ratio * _playback.duration))


def _scrub_click():
    global _scrubbing
    _scrubbing = True
    _seek_to_mouse()


# --- Cadre de composition -------------------------------------------------------

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


_SIDE_HANDLES = {"left", "right", "top", "bottom"}


def _handles(bounds, crop, rotation=0, *, corners_only=False):
    x, y, w, h = bounds
    points = {}
    if not crop or corners_only:
        points.update(top_left=(x, y), top_right=(x + w, y),
                      bottom_right=(x + w, y + h), bottom_left=(x, y + h))
    if not corners_only:
        points.update(left=(x, y + h / 2), right=(x + w, y + h / 2),
                      top=(x + w / 2, y), bottom=(x + w / 2, y + h))
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


def _is_empty():
    """Montage sans aucun clip : on invite à glisser un média dans le cadre."""
    if _editor is None:
        return True
    return not _editor.source_mode and not _editor.project.timeline.clips


def _draw_selection():
    global _selection_key
    clip = _editor.selected if _editor is not None and not _editor.source_mode else None
    if clip is not None and not (clip.timeline_start <= _time < clip.timeline_end):
        clip = None
    bounds = _bounds(clip) if clip is not None else None
    empty = _is_empty()
    crop = _crop_enabled(clip)
    rotation = _rotation(clip)
    can_rotate = clip is not None and _can_rotate(clip) and not crop
    key = (_size, bounds, crop, rotation, can_rotate, empty, _fullscreen)
    if key == _selection_key:
        return
    _selection_key = key
    dpg.delete_item(OVERLAY, children_only=True)
    if _fullscreen:  # visionnage seul : ni cadre, ni poignées
        return
    dpg.draw_rectangle((0, 0), _size, color=COLORS["viewer_frame"], parent=OVERLAY)
    if empty:
        tw = _text_width(DROP_HINT, 7.5)
        dpg.draw_text(((_size[0] - tw) / 2, _size[1] / 2 - 8), DROP_HINT, size=15,
                      color=COLORS["label_muted"], parent=OVERLAY)
        return
    if _editor is None or _editor.source_mode:
        return
    if clip is None:
        return
    sw, sh = _size
    color = (245, 180, 60, 255) if crop else (80, 180, 255, 255)
    corners = _handles(bounds, False, rotation, corners_only=True).values()
    dpg.draw_polygon([(px * sw, py * sh) for px, py in corners],
                     color=color, thickness=2, parent=OVERLAY)
    for name, (hx, hy) in _handles(bounds, crop, rotation).items():
        edge_resize = not crop and name in _SIDE_HANDLES
        size = 4 if edge_resize else 5
        fill = (140, 225, 250, 255) if edge_resize else color
        dpg.draw_rectangle((hx * sw - size, hy * sh - size), (hx * sw + size, hy * sh + size),
                           fill=fill, color=(255, 255, 255, 255), parent=OVERLAY,
                           tag=f"preview_handle_{name}")
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


def _target_at(point):
    """Même zone de prise pour le survol et le clic."""
    selected = _editor.selected
    clips = _editor.project.timeline.clips_at(_time)
    if selected is not None and selected in clips:
        bounds = _bounds(selected)
        crop = _crop_enabled(selected)
        rotation = _rotation(selected)
        handles = _handles(bounds, crop, rotation)
        rotation_handle = (
            _rotation_handle(bounds, rotation) if _can_rotate(selected) and not crop else None
        )
        if rotation_handle is not None:
            handles = {"rotate": rotation_handle[1], **handles}
        distance, nearest = min(
            (math.hypot((point[0] - x) * _size[0], (point[1] - y) * _size[1]), name)
            for name, (x, y) in handles.items()
        )
        if distance <= 9:
            return selected, nearest
        # Les bords entiers se comportent comme leurs poignées centrales.
        x, y, w, h = bounds
        px, py = _rotate_point(point, _bounds_center(bounds), -rotation)
        sw, sh = _size
        edges = []
        if x <= px <= x + w:
            edges.extend(((abs(py - y) * sh, "top"), (abs(py - y - h) * sh, "bottom")))
        if y <= py <= y + h:
            edges.extend(((abs(px - x) * sw, "left"), (abs(px - x - w) * sw, "right")))
        if edges:
            distance, nearest = min(edges)
            if distance <= 5:
                return selected, nearest
    for clip in reversed(clips):
        bounds = _bounds(clip)
        x, y, w, h = bounds
        px, py = _rotate_point(point, _bounds_center(bounds), -_rotation(clip))
        if x <= px <= x + w and y <= py <= y + h:
            return clip, "move"
    return None, None


def _gesture_cue(mode, handle, bounds, rotation):
    if handle in ("move", "rotate"):
        return handle, 0
    if handle in ("left", "right"):
        angle = 0
    elif handle in ("top", "bottom"):
        angle = 90
    else:
        _, _, w, h = bounds
        angle = math.degrees(math.atan2(h * _size[1], w * _size[0]))
        if handle in ("top_right", "bottom_left"):
            angle = -angle
    return mode, round((angle + rotation) % 180, 1)


def pointer_cue():
    can_seek = _duration() > 0
    if can_seek and _scrubbing:
        return "seek", 0
    if (_gesture is not None and _editor is not None
            and not _editor.source_mode and not _fullscreen):
        clip_id, original, bounds, _, mode, handle, _ = _gesture
        if _editor.selected_id == clip_id:
            return _gesture_cue(mode, handle, bounds, original.rotation)
    if dpg.is_mouse_button_down(dpg.mvMouseButton_Left):
        return None
    if can_seek and dpg.is_item_hovered(SCRUBBER):
        return "seek", 0
    if _editor is None or _editor.source_mode or _fullscreen:
        return None
    if not dpg.is_item_hovered(CANVAS):
        return None
    clip, handle = _target_at(_mouse())
    if clip is None:
        return None
    mode = "crop" if _crop_enabled(clip) else "resize"
    return _gesture_cue(mode, handle, _bounds(clip), _rotation(clip))


def _click():
    global _gesture
    if _editor is None or _editor.source_mode or _fullscreen:
        return
    point = _mouse()
    selected, handle = _target_at(point)
    _editor.select(selected.id if selected else None)
    if selected:
        _editor.playback.pause()
        time = _time - selected.timeline_start
        raw_box = selected.unzoomed_transform_at(time)
        _gesture = (selected.id, selected.transform_at(time), _bounds(selected), point,
                    "crop" if _crop_enabled(selected) else "resize", handle, raw_box)


def _drag():
    if _scrubbing:
        _seek_to_mouse()
        return
    if _gesture is None or _editor is None:
        return
    clip_id, original, bounds, origin, mode, handle, raw_box = _gesture
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
        if rotated_resize and transform is not base:
            # Ancrer le coin opposé dans le repère tourné, comme dans le cadre droit.
            center = _bounds_center((transform.x, transform.y, transform.width, transform.height))
            cx, cy = _rotate_point(center, _bounds_center(bounds), original.rotation)
            transform = replace(transform, x=transform.x + cx - center[0],
                                y=transform.y + cy - center[1])
        text_box = raw_box if isinstance(clip, TextClip) else None
        if mode == "resize" and handle in _SIDE_HANDLES:
            if text_box is not None:
                transform = replace(transform, stretch=text_box.stretch)
            if any(key.property == "zoom" for key in clip.keyframes):
                if transform != clip.transform_at(time):
                    _editor.resize_animated_box(transform, original.width / raw_box.width)
                return
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
    global _gesture, _scrubbing
    _gesture, _scrubbing = None, False


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
