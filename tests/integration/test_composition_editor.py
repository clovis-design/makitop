import dearpygui.dearpygui as dpg
import pytest

from makitop.application.composition import CompositionEditor
from makitop.application.projects import ProjectSession
from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.media.probe import probe
from makitop.model.composition import Transform, fitted_bounds, rotate_point
from makitop.storage.recent import RecentProjects
from makitop.ui import main_window
from makitop.ui.panels import media, preview, properties, timeline
from makitop.ui.panels.timeline import panel


@pytest.fixture
def editor(tmp_path):
    dpg.create_context()
    player = TimelinePlaybackController()
    session = ProjectSession(RecentProjects(tmp_path / "recent.json"))
    editor = CompositionEditor(session, player)
    errors = []
    main_window.build(playback_controller=player)
    preview.bind(editor, errors.append)
    properties.bind(editor, errors.append)
    timeline.bind(editor, errors.append)

    def refresh():
        preview.refresh()
        preview.update_time(player.current_time())
        properties.refresh()
        timeline.refresh()

    editor.on_refresh = refresh
    editor.show_montage(0)
    try:
        yield editor, errors
    finally:
        player.close()
        dpg.destroy_context()


def test_drop_video_photo_formats_properties_and_remove(
    editor, video_file, image_file, monkeypatch,
):
    editor, errors = editor
    monkeypatch.setattr(dpg, "get_text_size", lambda text: (len(text) * 8, 16))
    video, photo = probe(video_file), probe(image_file)
    editor.project.media.extend([video, photo])
    for item in (video, photo):
        media.add_media(item)
        assert dpg.get_item_children(f"media_item_{item.id}", 3)
        drop = dpg.get_item_configuration("composition_drop")["drop_callback"]
        drop(None, item.id)
    clips = editor.project.timeline.clips
    assert [c.track for c in clips] == [0, 1]
    assert [c.timeline_start for c in clips] == [0, 0]
    assert clips[1].duration == 5
    assert dpg.get_value("clip_name") == photo.name
    dpg.get_item_callback("composition_format")(None, "9:16")
    assert editor.project.canvas_format == "9:16"
    assert dpg.get_item_width(preview.CANVAS) < dpg.get_item_height(preview.CANVAS)
    dpg.get_item_callback("clip_image_duration")(None, 8)
    assert editor.selected.duration == 8
    editor.select(clips[0].id)
    dpg.get_item_callback("clip_volume")(None, 40)
    dpg.get_item_callback("clip_muted")(None, True)
    assert editor.selected.volume == 0.4
    assert editor.selected.muted
    dpg.get_item_callback("clip_start")(None, -1)
    assert errors and editor.selected.timeline_start == 0
    dpg.get_item_callback("clip_remove")()
    assert len(editor.project.timeline.clips) == 1
    assert editor.session.dirty


def test_mouse_move_resize_and_crop(editor, video_file, monkeypatch):
    editor, errors = editor
    clip = editor.add_media(probe(video_file))
    editor.update_clip(clip.id, transform=Transform(x=0.1, y=0.1, width=0.4, height=0.4))
    point = [0.3, 0.3]
    monkeypatch.setattr(preview, "_mouse", lambda: tuple(point))
    preview._click()
    point[:] = [0.4, 0.4]
    preview._drag()
    preview._release()
    assert editor.selected.transform.x == pytest.approx(0.25)
    # La source 4:3 est ajustée dans une boîte sur un cadre 16:9 : x initial = 0,15.
    before = editor.selected.transform
    x, y, w, h = fitted_bounds(before, 64, 48, 16 / 9)
    point[:] = [x + w, y + h]
    preview._click()
    point[:] = [x + w + 0.05, y + h + 0.05]
    preview._drag()
    preview._release()
    enlarged = editor.selected.transform
    assert enlarged.width > before.width
    assert enlarged.width / enlarged.height == pytest.approx(before.width / before.height)
    dpg.set_value("composition_crop", True)
    x, y, w, h = fitted_bounds(enlarged, 64, 48, 16 / 9)
    point[:] = [x, y + h / 2]
    preview._click()
    point[:] = [x + 0.04, y + h / 2]
    preview._drag()
    preview._release()
    assert editor.selected.transform.crop_left > 0
    assert editor.selected.transform.width < enlarged.width
    assert not errors


def test_inspector_transform_crop_and_effects(editor, video_file, monkeypatch):
    editor, errors = editor
    monkeypatch.setattr(dpg, "get_text_size", lambda text: (len(text) * 8, 16))
    editor.add_media(probe(video_file))
    dpg.get_item_callback("clip_zoom")(None, 50)
    assert editor.selected.transform.width == pytest.approx(0.5)
    assert dpg.get_value("clip_zoom") == pytest.approx(50)
    dpg.get_item_callback("clip_pos_x")(None, 10)
    assert editor.selected.transform.x == pytest.approx(0.35)
    crop = dpg.get_item_callback("clip_crop_left")
    crop(None, 20, "left")
    assert editor.selected.transform.crop_left == pytest.approx(0.2)
    assert dpg.get_value("clip_crop_left") == pytest.approx(20)
    before = editor.selected.transform
    dpg.get_item_callback("clip_zoom")(None, 900)
    assert errors and editor.selected.transform == before
    editor.add_effect("blur")
    assert dpg.get_value(properties.TABS) == properties.TAB_EFFECTS
    dpg.get_item_callback(properties.effect_slider_tag(0))(None, 20, (0, 100))
    assert editor.selected.effects[0].amount == pytest.approx(0.2)


def test_rotation_handle_and_mirror_controls(editor, video_file, monkeypatch):
    editor, errors = editor
    editor.add_media(probe(video_file))
    assert dpg.does_item_exist("preview_rotation_handle")
    dpg.get_item_callback("clip_flip_horizontal")(None, True)
    assert editor.selected.transform.flip_horizontal
    assert dpg.get_value("clip_flip_horizontal")
    dpg.get_item_callback("clip_flip_vertical")(None, True)
    assert editor.selected.transform.flip_vertical
    assert dpg.get_value("clip_flip_vertical")

    dpg.get_item_callback("clip_rotation")(None, 30)
    assert editor.selected.transform.rotation == 30
    editor.toggle_keyframe("x")
    editor.set_selected_keyframe_value(0.1)
    keys = editor.selected.keyframes
    bounds = preview._bounds(editor.selected)
    _, handle = preview._rotation_handle(bounds, 30)
    point = list(handle)
    monkeypatch.setattr(preview, "_mouse", lambda: tuple(point))
    preview._click()
    sw, sh = preview._size
    point[:] = rotate_point(handle, preview._bounds_center(bounds), 90, sw / sh)
    preview._drag()
    preview._release()
    assert editor.selected.transform.rotation == pytest.approx(120)
    assert dpg.get_value("clip_rotation") == pytest.approx(120)
    assert editor.selected.keyframes == keys
    assert editor.selected.transform.flip_horizontal
    assert editor.selected.transform.flip_vertical
    assert not errors


def test_timeline_drag_and_trim(editor, video_file, monkeypatch):
    editor, errors = editor
    clip = editor.add_media(probe(video_file))
    point = [50, panel._RULER_H + 30]
    monkeypatch.setattr(panel, "_mouse", lambda: point)
    panel._click()
    point[:] = [100, panel._RULER_H + 30]
    panel._drag()
    panel._release()
    assert editor.selected.timeline_start == 0.5
    assert editor.playback.current_time() == 0.5
    point[:] = [150, panel._RULER_H + 30]
    panel._click()
    point[:] = [125, panel._RULER_H + 30]
    panel._drag()
    panel._release()
    assert editor.selected.duration == pytest.approx(1 - 8 / 30)
    assert editor.selected.id == clip.id
    assert not errors


@pytest.mark.parametrize("kind,angle", [("video", 0), ("video", 90), ("text", 0)])
def test_preview_resize_axes_independently(editor, video_file, monkeypatch, kind, angle):
    editor, errors = editor
    if kind == "video":
        clip = editor.add_media(probe(video_file))
        if angle:
            editor.update_clip(clip.id, transform=Transform(x=0.2, y=0.2, width=0.6, height=0.6))
        editor.set_clip_orientation(rotation=angle)
    else:
        editor.add_text("title")
    point = []
    monkeypatch.setattr(preview, "_mouse", lambda: tuple(point))
    sw, sh = preview._size

    def drag(handle, delta):
        handles = preview._handles(preview._bounds(editor.selected), False, angle)
        point[:] = handles[handle]
        preview._click()
        dx, dy = rotate_point(delta, (0, 0), angle, sw / sh)
        point[:] = [point[0] + dx, point[1] + dy]
        preview._drag()
        preview._release()

    original = preview._bounds(editor.selected)
    left = preview._handles(original, False, angle)["left"]
    assert dpg.does_item_exist("preview_handle_right")
    assert dpg.does_item_exist("preview_handle_bottom")
    drag("right", (-0.12, 0.06))
    horizontal = preview._bounds(editor.selected)
    assert horizontal[2:] == pytest.approx((original[2] - 0.12, original[3]))
    assert preview._handles(horizontal, False, angle)["left"] == pytest.approx(left)
    top = preview._handles(horizontal, False, angle)["top"]
    drag("bottom", (0.06, -0.12))
    vertical = preview._bounds(editor.selected)
    assert vertical[2:] == pytest.approx((horizontal[2], horizontal[3] - 0.12))
    assert preview._handles(vertical, False, angle)["top"] == pytest.approx(top)
    assert editor.selected.transform.stretch == (kind == "video")
    assert not errors


def test_preview_vertical_resize_preserves_animated_zoom(editor, monkeypatch):
    editor, errors = editor
    editor.add_text("title")
    editor.toggle_keyframe("zoom")
    editor.set_selected_keyframe_value(0.6)
    bounds = preview._bounds(editor.selected)
    point = list(preview._handles(bounds, False)["bottom"])
    monkeypatch.setattr(preview, "_mouse", lambda: tuple(point))
    preview._click()
    point[1] -= 0.1
    preview._drag()
    preview._release()
    assert preview._bounds(editor.selected)[2:] == pytest.approx((0.6, bounds[3] - 0.1))
    assert editor.selected.keyframes[0].value == pytest.approx(0.6)
    assert not errors
