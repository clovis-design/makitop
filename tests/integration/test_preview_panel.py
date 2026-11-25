import dearpygui.dearpygui as dpg
import pytest

from makitop.application.composition import CompositionEditor
from makitop.application.projects import ProjectSession
from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.media.probe import probe
from makitop.model.composition import Transform
from makitop.storage.recent import RecentProjects
from makitop.ui import main_window, shortcuts
from makitop.ui.panels import preview, properties, transport_icons


@pytest.fixture
def editor(tmp_path):
    dpg.create_context()
    player = TimelinePlaybackController()
    session = ProjectSession(RecentProjects(tmp_path / "recent.json"))
    editor = CompositionEditor(session, player)
    main_window.build(playback_controller=player)
    preview.bind(editor, lambda message: None)

    def refresh():
        preview.refresh()
        preview.update_time(player.current_time())

    editor.on_refresh = refresh
    editor.show_montage(0)
    main_window.resize(1600, 900)
    try:
        yield editor
    finally:
        player.close()
        dpg.destroy_context()


@pytest.mark.parametrize("seconds,fps,expected", [
    (0, 30, "00:00:00:00"),
    (3725.5, 30, "01:02:05:15"),
    (59.99, 25, "00:00:59:24"),
    (-1, 60, "00:00:00:00"),
])
def test_format_time_is_a_resolve_timecode(seconds, fps, expected):
    assert preview.format_time(seconds, fps) == expected


def test_scrubber_click_seeks_proportionally(editor, video_file, monkeypatch):
    editor.add_media(probe(video_file))
    duration = editor.playback.duration
    assert duration > 0
    monkeypatch.setattr(preview, "_mouse_scrub", lambda: 0.5)
    preview._scrub_click()
    assert editor.playback.current_time() == pytest.approx(duration / 2, abs=0.05)
    monkeypatch.setattr(preview, "_mouse_scrub", lambda: 0.0)
    preview._drag()
    assert editor.playback.current_time() == pytest.approx(0, abs=0.05)
    preview._release()
    assert not preview._scrubbing


def test_pointer_follows_preview_handles_and_keeps_active_gesture(editor, video_file, monkeypatch):
    clip = editor.add_media(probe(video_file))
    editor.update_clip(clip.id, transform=Transform(x=0.2, y=0.2, width=0.6, height=0.6))
    hovered = preview.CANVAS
    point = (0.5, 0.5)
    monkeypatch.setattr(dpg, "is_item_hovered", lambda item: item == hovered)
    monkeypatch.setattr(preview, "_mouse", lambda: point)
    assert preview.pointer_cue() == ("move", 0)

    bounds = preview._bounds(editor.selected)
    handles = preview._handles(bounds, False)
    for name, angle in (("left", 0), ("bottom", 90)):
        point = handles[name]
        assert preview.pointer_cue() == ("resize", angle)
    x, y, w, h = bounds
    point = (x + w, y + h * 0.25)
    assert preview.pointer_cue() == ("resize", 0)
    point = handles["bottom_right"]
    kind, angle = preview.pointer_cue()
    assert kind == "resize" and 0 < angle < 90
    point = preview._rotation_handle(bounds, 0)[1]
    assert preview.pointer_cue() == ("rotate", 0)
    preview._click()
    hovered = preview.SCRUBBER
    assert preview.pointer_cue() == ("rotate", 0)
    preview._release()
    assert preview.pointer_cue() == ("seek", 0)

    hovered = preview.CANVAS
    editor.set_clip_orientation(rotation=90)
    bounds = preview._bounds(editor.selected)
    point = preview._handles(bounds, False, 90)["left"]
    assert preview.pointer_cue() == ("resize", 90)
    dpg.set_value("composition_crop", True)
    assert preview.pointer_cue() == ("crop", 90)
    preview.set_fullscreen(True)
    assert preview.pointer_cue() is None


def test_pointer_for_text_only_in_preview(editor, monkeypatch):
    editor.add_text("title")
    hovered = preview.CANVAS
    point = preview._handles(preview._bounds(editor.selected), False)["top"]
    monkeypatch.setattr(preview, "_mouse", lambda: point)
    monkeypatch.setattr(dpg, "is_item_hovered", lambda item: item == hovered)
    assert preview.pointer_cue() == ("resize", 90)
    hovered = None
    assert preview.pointer_cue() is None


def test_show_montage_button_only_in_source_mode(editor, video_file):
    assert not dpg.get_item_configuration("composition_show")["show"]
    assert dpg.get_value("preview_mode") == "MONTAGE"
    editor.preview_source(probe(video_file))
    assert dpg.get_item_configuration("composition_show")["show"]
    assert dpg.get_value("preview_mode") == "SOURCE"


@pytest.mark.parametrize("fmt", ["16:9", "9:16", "1:1"])
def test_canvas_is_centered_inside_viewer(editor, fmt):
    dpg.get_item_callback("composition_format")(None, fmt)
    viewer_w = dpg.get_item_width(preview.VIEWER)
    viewer_h = dpg.get_item_height(preview.VIEWER)
    canvas_w = dpg.get_item_width(preview.CANVAS)
    canvas_h = dpg.get_item_height(preview.CANVAS)
    pad_x = dpg.get_item_width(preview.VIEWER_PAD_X)
    pad_y = dpg.get_item_height(preview.VIEWER_PAD_Y)
    assert canvas_w <= viewer_w and canvas_h <= viewer_h
    assert pad_x >= 0 and pad_y >= 0
    assert abs(2 * pad_x + canvas_w - viewer_w) <= 1
    assert abs(2 * pad_y + canvas_h - viewer_h) <= 1


def _id(item):
    """Dear PyGui renvoie l'alias ou l'identifiant numérique selon les cas."""
    return item if isinstance(item, int) else dpg.get_alias_id(item)


def test_fullscreen_button_moves_viewer_and_restores_layout(editor):
    toggle = dpg.get_item_callback(preview.FULLSCREEN_BUTTON)
    toggle()
    assert main_window.is_fullscreen() and preview.is_fullscreen()
    assert _id(dpg.get_item_parent(preview.TAG)) == _id(main_window.FULLSCREEN_WINDOW)
    assert not dpg.get_item_configuration(preview.HEADER)["show"]
    assert not dpg.get_item_configuration(main_window.ROOT)["show"]
    texture = dpg.get_item_configuration(preview.FULLSCREEN_BUTTON)["texture_tag"]
    assert _id(texture) == _id(transport_icons.texture_tag("exit_fullscreen"))

    main_window.resize(1600, 900)
    assert dpg.get_item_width(preview.TAG) == 1600
    assert dpg.get_item_height(preview.TAG) == 900
    assert dpg.get_item_width(preview.CANVAS) <= dpg.get_item_width(preview.VIEWER)
    assert dpg.get_item_height(preview.CANVAS) <= dpg.get_item_height(preview.VIEWER)

    toggle()
    assert not main_window.is_fullscreen() and not preview.is_fullscreen()
    assert [_id(i) for i in dpg.get_item_children(main_window.TOP_ROW, 1)] == [
        _id(preview.TAG), _id(properties.TAG)]
    assert dpg.get_item_configuration(preview.HEADER)["show"]
    assert dpg.get_item_configuration(main_window.ROOT)["show"]


def test_text_input_active_blocks_single_key_shortcuts(editor, monkeypatch):
    assert not shortcuts.text_input_active()
    search = dpg.get_alias_id("media_search_input")
    monkeypatch.setattr(dpg, "is_item_active", lambda item: item == search)
    assert shortcuts.text_input_active()
