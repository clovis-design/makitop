import dearpygui.dearpygui as dpg
import pytest

from makitop.application.composition import CompositionEditor
from makitop.application.projects import ProjectSession
from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.media.probe import probe
from makitop.storage.recent import RecentProjects
from makitop.ui.panels import properties, timeline
from makitop.ui.panels.timeline import panel


@pytest.fixture
def editor(tmp_path, monkeypatch):
    dpg.create_context()
    player = TimelinePlaybackController()
    session = ProjectSession(RecentProjects(tmp_path / "recent.json"))
    editor = CompositionEditor(session, player)
    errors = []
    monkeypatch.setattr(dpg, "get_text_size", lambda text: (len(text) * 8, 16))
    try:
        with dpg.window():
            properties.create()
            timeline.create()
        properties.bind(editor, errors.append)
        timeline.bind(editor, errors.append)
        editor.on_refresh = lambda: (properties.refresh(), timeline.refresh())
        yield editor, errors
    finally:
        player.close()
        dpg.destroy_context()


def test_properties_create_animate_and_select_keyframes(editor, image_file):
    editor, errors = editor
    editor.add_media(probe(image_file))
    dpg.get_item_callback("keyframe_add_x")(None, None, "x")
    editor.seek(2)
    dpg.get_item_callback("clip_x")(None, 50, "x")
    assert [(k.time, k.value) for k in editor.selected.keyframes] == [(0, 0), (2, 0.5)]
    assert editor.selected.transform_at(1).x == 0.25
    assert dpg.get_item_label("keyframe_add_x") == "- clé"
    assert len(list(panel._key_positions())) == 2
    assert editor.selected.id in timeline.get_clip_ids()  # images fixes aussi
    editor.seek(1)
    properties.tick(1)
    assert dpg.get_value("clip_x") == 25
    editor.adjacent_keyframe(1)
    assert editor.selected_keyframe == ("x", 2)
    dpg.get_item_callback("keyframe_interpolation")(None, "Douce")
    editor.adjacent_keyframe(-1)
    dpg.get_item_callback("keyframe_interpolation")(None, "Douce")
    assert editor.selected.transform_at(0.5).x == pytest.approx(0.078125)
    assert not errors


def test_timeline_drag_delete_collision_and_toggle(editor, image_file, monkeypatch):
    editor, errors = editor
    editor.add_media(probe(image_file))
    editor.toggle_keyframe("x")
    editor.seek(2)
    editor.set_animated_value("x", 0.5)
    key, x, y = next(p for p in panel._key_positions() if p[0].time == 2)
    assert panel._keyframe_at(x, y) == key
    assert dpg.does_item_exist(f"keyframe_{editor.selected_id}_x_2.0")
    down, mouse = [True], [x, y]
    monkeypatch.setattr(dpg, "is_mouse_button_down", lambda _: down[0])
    monkeypatch.setattr(dpg, "is_item_hovered", lambda _: True)
    monkeypatch.setattr(dpg, "get_mouse_pos", lambda **_: mouse)
    monkeypatch.setattr(dpg, "get_item_state", lambda _: {"rect_min": (0, 0)})
    panel.tick()
    assert editor.selected_keyframe == ("x", 2)
    assert panel._drag_clip is None
    mouse[0] = 3 * panel._px_per_sec
    panel.tick()
    down[0] = False
    panel.tick()
    assert editor.selected_keyframe == ("x", 3)
    assert sorted(k.time for k in editor.selected.keyframes) == [0, 3]
    assert editor.selected.timeline_start == 0
    with pytest.raises(ValueError, match="déjà"):
        editor.move_keyframe("x", 3, 0)
    assert len(editor.selected.keyframes) == 2
    dpg.get_item_callback("timeline_delete_keyframe")()
    assert len(editor.selected.keyframes) == 1
    panel._toggle_keyframes(None, False)
    assert list(panel._key_positions()) == []
    assert not errors


def test_transform_gesture_updates_animation_and_reset(editor, image_file):
    from dataclasses import replace

    editor, errors = editor
    editor.add_media(probe(image_file))
    editor.toggle_keyframe("x")
    editor.seek(2)
    editor.update_clip(editor.selected_id, transform=replace(editor.selected.transform, x=0.4))
    assert editor.selected.transform_at(1).x == pytest.approx(0.2)
    assert editor.selected.transform.x == 0
    editor.toggle_keyframe("volume")
    editor.reset_transform()
    assert [k.property for k in editor.selected.keyframes] == ["volume"]
    assert editor.selected.transform.x == 0
    assert not errors
