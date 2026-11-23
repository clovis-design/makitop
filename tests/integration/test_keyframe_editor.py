from dataclasses import replace

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
    assert not dpg.get_value("timeline_show_keyframes")
    assert list(panel._key_positions()) == []
    dpg.get_item_callback("timeline_show_keyframes")("timeline_show_keyframes", True)
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
    panel._toggle_keyframes(None, True)
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


def test_zoom_keyframes_lock_regular_zoom_control_until_last_key_is_removed(editor, image_file):
    editor, errors = editor
    editor.add_media(probe(image_file))
    dpg.get_item_callback("keyframe_add_zoom")(None, None, "zoom")
    editor.seek(2)
    dpg.get_item_callback("keyframe_add_zoom")(None, None, "zoom")
    dpg.get_item_callback("keyframe_value")(None, 200)
    assert editor.selected.transform_at(1).width == pytest.approx(1.5)
    assert dpg.get_value("clip_zoom") == pytest.approx(200)
    panel._toggle_keyframes(None, True)
    assert len(list(panel._key_positions())) == 2
    assert not dpg.is_item_enabled("clip_zoom")
    assert not dpg.is_item_shown("clip_zoom")
    display = "inspector_animated_clip_zoom"
    assert dpg.is_item_shown(display)
    assert dpg.is_item_enabled(display)
    assert dpg.get_item_label(display) == "200.0 %   ◆ Animé ›"
    assert not dpg.is_item_enabled("inspector_reset_transform")
    assert dpg.is_item_shown("inspector_animation_hint_video")

    editor.seek(1)
    properties.tick(1)
    assert dpg.get_value("clip_zoom") == pytest.approx(150)
    assert dpg.get_item_label(display) == "150.0 %   ◆ Animé ›"
    dpg.get_item_callback("clip_zoom")(None, 75)
    assert [k.time for k in editor.selected.keyframes] == [0, 2]
    editor.seek(1.8)
    dpg.set_value(properties.TABS, properties.TAB_VIDEO)
    dpg.get_item_callback(display)(None, None, dpg.get_item_user_data(display))
    assert dpg.get_value(properties.TABS) == properties.TAB_KEYFRAMES
    assert editor.selected_keyframe == ("zoom", 2)
    assert editor.playback.current_time() == pytest.approx(2)
    assert dpg.get_value("keyframe_value") == pytest.approx(200)
    assert [k.time for k in editor.selected.keyframes] == [0, 2]
    editor.seek(1)
    editor.toggle_keyframe("zoom")
    dpg.get_item_callback("keyframe_value")(None, 75)
    assert editor.selected_keyframe == ("zoom", 1)
    assert [(k.property, k.time, k.value) for k in editor.selected.keyframes] == [
        ("zoom", 0, 1), ("zoom", 1, 0.75), ("zoom", 2, 2),
    ]
    assert editor.selected.transform_at(1).width == pytest.approx(0.75)
    assert editor.selected.transform_at(1).x == pytest.approx(0.125)
    for time in (1, 2, 0):
        editor.seek(time)
        editor.toggle_keyframe("zoom")
    assert not editor.selected.keyframes
    assert dpg.is_item_enabled("clip_zoom")
    assert dpg.is_item_shown("clip_zoom")
    assert not dpg.is_item_shown(display)
    dpg.get_item_callback("clip_zoom")(None, 75)
    assert editor.selected.transform.width == pytest.approx(0.75)
    assert not errors


def test_unanimated_video_controls_do_not_change_animated_axes_or_volume(editor, video_file):
    editor, errors = editor
    editor.add_media(probe(video_file))
    editor.toggle_keyframe("x")
    editor.set_selected_keyframe_value(0.4)
    editor.toggle_keyframe("volume")
    editor.set_selected_keyframe_value(0.5)
    assert not dpg.is_item_enabled("clip_pos_x")
    assert dpg.is_item_enabled("clip_pos_y")
    assert not dpg.is_item_enabled("clip_volume")
    assert dpg.is_item_enabled("clip_muted")

    editor.seek(0.5)
    keys = editor.selected.keyframes
    dpg.get_item_callback("clip_pos_y")(None, 10)
    dpg.get_item_callback("clip_volume")(None, 90)
    assert editor.selected.transform.y == pytest.approx(0.1)
    assert editor.selected.keyframes == keys
    assert editor.selected.volume_at(0.5) == pytest.approx(0.5)
    assert not errors


def test_text_tab_order_and_animation_locks_follow_selected_clip(editor, image_file):
    editor, errors = editor
    tabs = dpg.get_item_children(properties.TABS, 1)
    assert tabs.index(dpg.get_alias_id(properties.TAB_TEXT)) < tabs.index(
        dpg.get_alias_id(properties.TAB_KEYFRAMES)
    )
    title = editor.add_text("title")
    assert dpg.is_item_enabled("clip_text_height")
    editor.toggle_keyframe("height")
    editor.set_selected_keyframe_value(0.25)
    assert not dpg.is_item_enabled("clip_text_height")
    assert dpg.is_item_enabled("clip_text_width")
    assert dpg.is_item_shown("clip_text_width")
    display = "inspector_animated_clip_text_height"
    assert dpg.get_item_label(display) == "25.0 %   ◆ Animé ›"
    dpg.get_item_callback(display)(None, None, dpg.get_item_user_data(display))
    assert dpg.get_value(properties.TABS) == properties.TAB_KEYFRAMES
    assert editor.selected_keyframe == ("height", 0)
    assert dpg.is_item_enabled("keyframe_value")
    dpg.get_item_callback("clip_text_height")(None, 50, "height")
    assert editor.selected.transform_at(0).height == pytest.approx(0.25)
    assert dpg.is_item_shown("inspector_animation_hint_text")

    editor.add_text("paragraph")
    assert dpg.is_item_enabled("clip_text_height")
    editor.select(title.id)
    assert not dpg.is_item_enabled("clip_text_height")
    editor.toggle_keyframe("height")
    assert dpg.is_item_enabled("clip_text_height")
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


def test_speed_control_retimes_duration_and_keyframes(editor, video_file, image_file):
    editor, errors = editor
    video = replace(probe(video_file), duration=120.0)
    editor.add_media(video)
    assert dpg.is_item_shown("clip_speed_row")
    assert dpg.get_item_type("clip_speed") == "mvAppItemType::mvSliderInt"
    data = dpg.get_item_user_data("clip_speed")
    choices = data[1]
    assert dpg.get_value("clip_speed") == choices.index(1.0)
    assert dpg.get_item_configuration("clip_speed")["format"] == "1×"
    assert dpg.get_value("clip_speed_duration") == "2 min 00.00 s"
    editor.seek(20)
    editor.toggle_keyframe("x")

    change_speed = dpg.get_item_callback("clip_speed")
    change_speed(None, choices.index(2.0), data)
    clip = editor.selected
    assert (clip.source_start, clip.source_end) == (0, 120)
    assert clip.duration == 60
    assert editor.playback.duration == 60
    assert editor.playback.current_time() == 10
    assert dpg.get_value("clip_speed_duration") == "1 min 00.00 s"
    assert editor.selected_keyframe == ("x", 10)
    assert clip.keyframes[0].time == 10

    change_speed(None, -1, data)
    assert editor.selected == clip
    assert dpg.get_item_configuration("clip_speed")["format"] == "2×"

    editor.set_clip_speed(1.75)
    data = dpg.get_item_user_data("clip_speed")
    assert data[1][dpg.get_value("clip_speed")] == 1.75
    assert dpg.get_item_configuration("clip_speed")["format"] == "1,75×"
    change_speed(None, data[1].index(1.0), data)
    assert editor.selected.duration == 120
    assert not errors
    editor.add_media(probe(image_file))
    assert not dpg.is_item_shown("clip_speed_row")
