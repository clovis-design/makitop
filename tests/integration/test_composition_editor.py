import dearpygui.dearpygui as dpg
import pytest

from makitop.application.composition import CompositionEditor
from makitop.application.projects import ProjectSession
from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.media.probe import probe
from makitop.model.composition import Transform, fitted_bounds
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
