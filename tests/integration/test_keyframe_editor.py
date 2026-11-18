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
    assert not dpg.get_item_configuration("keyframe_row_volume")["show"]
    dpg.get_item_callback("keyframe_add_x")(None, None, "x")
    editor.seek(2)
    dpg.get_item_callback("keyframe_add_x")(None, None, "x")
    assert dpg.get_value("keyframe_value") == 0
    dpg.get_item_callback("keyframe_value")(None, 50)
    assert [(k.time, k.value) for k in editor.selected.keyframes] == [(0, 0), (2, 0.5)]
    assert editor.selected.transform_at(1).x == 0.25
    assert not dpg.does_item_exist("clip_x")
    assert not dpg.does_item_exist("clip_volume_kf")
    assert dpg.get_item_label("keyframe_add_x") == "◆"
    assert dpg.get_value("keyframe_hint_x") == "Retirer une clé « Position X » à 2.000 s"
    assert dpg.does_item_exist(f"key_badge_{editor.selected_id}")
    assert not dpg.does_item_exist("timeline_delete_keyframe")
    assert len(list(panel._key_positions())) == 2
    assert editor.selected.id in timeline.get_clip_ids()  # images fixes aussi
    editor.seek(1)
    properties.tick(1)
    assert dpg.get_value("keyframe_value") == 50
    # L'édition cible la clé sélectionnée, pas l'instant actuel (1 s).
    dpg.get_item_callback("keyframe_value")(None, 60)
    assert [(k.time, k.value) for k in editor.selected.keyframes] == [(0, 0), (2, 0.6)]
    assert dpg.get_value("keyframe_value") == 60
    dpg.get_item_callback("keyframe_value")(None, 50)
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
    assert dpg.get_item_label("keyframe_add_x") == "◆"
    dpg.get_item_callback("keyframe_add_x")(None, None, "x")
    assert len(editor.selected.keyframes) == 1
    assert dpg.get_item_label("keyframe_add_x") == "◇"
    panel._toggle_keyframes(None, False)
    assert list(panel._key_positions()) == []
    assert not errors


def test_video_with_audio_shows_volume_and_transform_controls(editor, video_file):
    editor, errors = editor
    editor.add_media(probe(video_file))
    assert dpg.get_item_configuration("keyframe_row_volume")["show"]
    assert dpg.get_item_configuration("keyframe_row_x")["show"]
    dpg.get_item_callback("keyframe_add_volume")(None, None, "volume")
    assert dpg.get_value("keyframe_value") == 100
    dpg.get_item_callback("keyframe_value")(None, 25)
    assert editor.selected.keyframes[0].value == 0.25
    assert editor.selected.keyframes[0].property == "volume"
    assert not errors


def test_selected_keyframe_value_rejects_invalid_values(editor, image_file):
    editor, errors = editor
    editor.add_media(probe(image_file))
    dpg.get_item_callback("keyframe_add_width")(None, None, "width")
    initial_value = editor.selected.keyframes[0].value
    dpg.get_item_callback("keyframe_value")(None, 0)
    assert editor.selected.keyframes[0].value == initial_value
    assert dpg.get_value("keyframe_value") == initial_value * 100
    assert errors


def test_zoom_keyframes_from_inspector_and_zoom_control(editor, image_file):
    editor, errors = editor
    editor.add_media(probe(image_file))
    dpg.get_item_callback("keyframe_add_zoom")(None, None, "zoom")
    editor.seek(2)
    dpg.get_item_callback("keyframe_add_zoom")(None, None, "zoom")
    dpg.get_item_callback("keyframe_value")(None, 200)
    assert editor.selected.transform_at(1).width == pytest.approx(1.5)
    assert dpg.get_value("clip_zoom") == pytest.approx(200)
    assert len(list(panel._key_positions())) == 2

    editor.seek(1)
    dpg.get_item_callback("clip_zoom")(None, 75)
    assert editor.selected_keyframe == ("zoom", 1)
    assert [(k.property, k.time, k.value) for k in editor.selected.keyframes] == [
        ("zoom", 0, 1), ("zoom", 1, 0.75), ("zoom", 2, 2),
    ]
    assert editor.selected.transform_at(1).width == pytest.approx(0.75)
    assert editor.selected.transform_at(1).x == pytest.approx(0.125)
    editor.reset_transform()
    assert not editor.selected.keyframes
    assert not errors


def test_keyframe_and_effect_badges_on_each_clip(editor, image_file):
    editor, errors = editor
    media = probe(image_file)
    editor.add_media(media)
    first_id = editor.selected_id
    editor.toggle_keyframe("x")
    editor.add_media(media, start=10)
    second_id = editor.selected_id
    editor.toggle_keyframe("y")
    editor.update_clip(second_id, track=next(
        clip.track for clip in editor.project.timeline.clips if clip.id == first_id))
    assert len(panel.get_track_rows()) == 1
    assert dpg.does_item_exist(f"key_badge_{first_id}")
    assert dpg.does_item_exist(f"key_badge_{second_id}")

    # Le badge reste visible quand les lignes d'animation sont repliées.
    panel._toggle_keyframes(None, False)
    assert dpg.does_item_exist(f"key_badge_{first_id}")
    assert dpg.does_item_exist(f"key_badge_{second_id}")

    from makitop.model.effects import Effect
    editor.update_clip(first_id, effects=(Effect("brightness", 0.3),))
    assert dpg.does_item_exist(f"fx_badge_{first_id}")
    assert dpg.does_item_exist(f"key_badge_{first_id}")
    assert not dpg.does_item_exist(f"fx_badge_{second_id}")
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
