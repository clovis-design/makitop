import json
from dataclasses import replace

import av
import dearpygui.dearpygui as dpg
import numpy as np
import pytest

from makitop.application.composition import CompositionEditor
from makitop.application.projects import ProjectSession
from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.engine.text import load_font
from makitop.engine.timeline import TimelineRenderer
from makitop.export.mp4 import ExportSettings, export_mp4
from makitop.media.probe import probe
from makitop.model.keyframes import Keyframe
from makitop.model.project import Project
from makitop.model.text import FONTS, PRESETS
from makitop.model.timeline import ImageClip, TextClip, Timeline
from makitop.storage.project_file import load, save
from makitop.storage.recent import RecentProjects
from makitop.ui import main_window
from makitop.ui.panels import media, preview, properties, sidebar, text_presets, timeline
from makitop.ui.panels.timeline import panel


def _edit(tag, value):
    dpg.set_value(tag, value)
    dpg.get_item_callback(tag)(tag, value)


def test_text_presets_timeline_and_inspector(tmp_path, image_file, monkeypatch):
    dpg.create_context()
    player = TimelinePlaybackController()
    editor = CompositionEditor(ProjectSession(RecentProjects(tmp_path / "recent.json")), player)
    errors = []
    try:
        main_window.build(playback_controller=player, on_add_text=editor.add_text)
        preview.bind(editor, errors.append)
        properties.bind(editor, errors.append)
        timeline.bind(editor, errors.append)
        editor.on_refresh = lambda: (preview.refresh(), properties.refresh(), timeline.refresh())
        image = editor.add_media(probe(image_file))
        editor.seek(1)
        sidebar.select("text")
        assert dpg.is_item_shown(media.section_tag("text"))
        assert all(dpg.get_item_type(text_presets.button_tag(key)) == "mvAppItemType::mvImageButton"
                   for key in PRESETS)
        dpg.get_item_callback("text_preset_title")(None, None, "title")
        title = editor.selected
        assert isinstance(title, TextClip)
        assert title.timeline_start == 1
        assert timeline.get_track_rows() == [[title.id], [image.id]]
        assert editor.project.timeline.clips_at(2) == [image, title]
        assert dpg.is_item_shown(properties.TAB_TEXT)
        assert dpg.is_item_shown(properties.TAB_KEYFRAMES)
        assert not dpg.is_item_shown(properties.TAB_VIDEO)
        assert dpg.get_value(properties.TABS) == properties.TAB_TEXT

        _edit(properties.TEXT_CONTENT, "Mon titre\nsur deux lignes")
        _edit("clip_text_size", 90)
        _edit("clip_text_alignment", "Gauche")
        _edit("clip_text_font", "DejaVu Serif")
        sender = "clip_text_display_duration"
        dpg.get_item_callback(sender)(sender, 3.0, "display_duration")
        sender = "clip_text_color"
        dpg.set_value(sender, (255, 230, 120, 255))
        dpg.get_item_callback(sender)(sender)
        sender = "clip_text_x"
        dpg.get_item_callback(sender)(sender, 20.0, "x")
        title = editor.selected
        assert title.content == "Mon titre\nsur deux lignes"
        assert title.style.size == 90
        assert title.style.font == "serif"
        assert title.style.alignment == "left"
        assert title.style.color == (255, 230, 120)
        assert title.duration == 3
        assert preview._bounds(title)[0] == pytest.approx(0.2)

        editor.select(image.id)
        preview.update_time(2)
        point = [0.5, 0.5]
        monkeypatch.setattr(preview, "_mouse", lambda: tuple(point))
        preview._click()
        assert editor.selected_id == title.id
        point[0] += 0.1
        preview._drag()
        preview._release()
        assert editor.selected.transform.x == pytest.approx(0.3)

        down = [True]
        mouse = [title.timeline_start * panel._px_per_sec + 10, panel._row_top(0) + 20]
        monkeypatch.setattr(dpg, "is_mouse_button_down", lambda _: down[0])
        monkeypatch.setattr(dpg, "is_item_hovered", lambda _: True)
        monkeypatch.setattr(dpg, "get_mouse_pos", lambda **_: mouse)
        monkeypatch.setattr(dpg, "get_item_state", lambda _: {"rect_min": (0, 0)})
        panel.tick()
        mouse[0] += panel._px_per_sec
        mouse[1] = panel._row_top(1) + 20
        panel.tick()
        down[0] = False
        panel.tick()
        assert editor.selected.timeline_start == 2
        assert timeline.get_track_rows() == [[image.id], [title.id]]
        assert [c.id for c in editor.project.timeline.clips_at(3)] == [title.id, image.id]
        dpg.get_item_callback("clip_text_track_front")()
        assert timeline.get_track_rows() == [[title.id], [image.id]]
        assert [c.id for c in editor.project.timeline.clips_at(3)] == [image.id, title.id]

        dpg.set_value(properties.TABS, properties.TAB_KEYFRAMES)
        assert dpg.is_item_shown("keyframe_row_opacity")
        assert not dpg.is_item_shown("keyframe_row_volume")
        editor.seek(2)
        dpg.get_item_callback("keyframe_add_opacity")(None, None, "opacity")
        dpg.get_item_callback("keyframe_value")(None, 0)
        dpg.get_item_callback("keyframe_add_x")(None, None, "x")
        editor.seek(4)
        dpg.get_item_callback("keyframe_add_opacity")(None, None, "opacity")
        dpg.get_item_callback("keyframe_value")(None, 100)
        dpg.get_item_callback("keyframe_add_x")(None, None, "x")
        dpg.get_item_callback("keyframe_value")(None, 50)
        animated = editor.selected
        assert animated.opacity_at(1) == pytest.approx(0.5)
        assert animated.transform_at(1).x == pytest.approx(0.4)
        panel._toggle_keyframes(None, True)
        assert len(list(panel._key_positions())) == 4
        assert dpg.get_value(properties.TABS) == properties.TAB_KEYFRAMES
        dpg.set_value(properties.TABS, properties.TAB_TEXT)

        editor.seek(2)
        subtitle = editor.add_text("subtitle")
        assert subtitle.track != title.track
        assert timeline.get_track_rows() == [[subtitle.id], [title.id], [image.id]]
        editor.seek(7)
        dpg.get_item_callback("text_preset_terminal")(None, None, "terminal")
        terminal = editor.selected
        assert terminal.content == PRESETS["terminal"].content
        assert terminal.style.font == "mono"
        assert dpg.get_value("clip_text_font") == "DejaVu Sans Mono"
        assert terminal.track == animated.track
        assert timeline.get_track_rows() == [[subtitle.id], [title.id, terminal.id], [image.id]]
        editor.remove_selected()
        editor.select(image.id)
        assert not dpg.is_item_shown(properties.TAB_TEXT)
        assert dpg.is_item_shown(properties.TAB_VIDEO)
        assert dpg.get_value(properties.TABS) == properties.TAB_VIDEO
        assert not errors
    finally:
        player.close()
        dpg.destroy_context()


def test_text_catalog_covers_presets_with_distinct_icons():
    kinds = [kind for group in text_presets.GROUPS.values() for kind in group]
    assert len(kinds) == len(PRESETS) == 12
    assert set(kinds) == set(PRESETS)
    thumbs = [text_presets.thumbnail(kind) for kind in kinds]
    assert len({thumb.tobytes() for thumb in thumbs}) == len(kinds)
    assert all(thumb.shape == (84 * 47 * 4,) and thumb.dtype == np.float32 for thumb in thumbs)
    assert {preset.style.font for preset in PRESETS.values()} == set(FONTS.values())
    for bold in (True, False):
        names = {load_font(font, 24, bold).getname() for font in FONTS.values()}
        assert len(names) == len(FONTS)
        assert ("DejaVu Sans Mono", "Bold" if bold else "Book") in names


def test_text_round_trip_render_and_export(tmp_path, image_file):
    image_media = probe(image_file)
    image = ImageClip(0, image_media, .4, track=8)
    preset = PRESETS["title"]
    title = TextClip(.1, .2, "Bonjour !", style=preset.style, transform=preset.box, track=9)
    project = Project(media=[image_media], timeline=Timeline(fps=10, clips=[title, image]))
    path = tmp_path / "montage.makitop"
    save(project, path)
    project = load(path)
    assert project.timeline.clips[0] == title
    assert project.missing_media() == []

    renderer = TimelineRenderer(640, 360)
    try:
        before = renderer.render(project, 0)
        within = renderer.render(project, 1)
        after = renderer.render(project, 3)
        assert np.array_equal(before, after)
        assert not (before[:, :, 1] > 200).any()
        assert (within[:, :, 1] > 200).sum() > 100
        restored_title = project.timeline.clips[0]
        project.timeline.clips[0] = replace(restored_title, track=0)
        assert np.array_equal(renderer.render(project, 1), before)
        project.timeline.clips[0] = restored_title
    finally:
        renderer.close()

    video = export_mp4(project, tmp_path / "montage.mp4", settings=ExportSettings(height=360))
    with av.open(str(video)) as container:
        pixels = [frame.to_ndarray(format="rgb24") for frame in container.decode(video=0)]
    assert len(pixels) == 4
    assert not (pixels[0][:, :, 1] > 200).any()
    assert (pixels[1][:, :, 1] > 200).sum() > 100
    assert not (pixels[3][:, :, 1] > 200).any()


def test_legacy_text_stays_in_front_and_animated_opacity_is_rendered(tmp_path, image_file):
    media = probe(image_file)
    image = ImageClip(0, media, 1.1, track=8)
    preset = PRESETS["title"]
    title = TextClip(0, 1.1, "Bonjour", style=preset.style, transform=preset.box, track=0)
    project = Project(media=[media], timeline=Timeline(fps=10, clips=[image, title]))
    path = tmp_path / "legacy.makitop"
    save(project, path)
    data = json.loads(path.read_text())
    data["version"] = 6
    del data["timeline"][1]["style"]["font"]
    path.write_text(json.dumps(data))
    project = load(path)
    image, title = project.timeline.clips
    assert title.track > image.track
    assert title.style.font == "inter"
    title = replace(title, style=replace(title.style, font="serif_italic"))
    project.timeline.clips[1] = replace(title, keyframes=(
        Keyframe("opacity", 0, 0), Keyframe("opacity", 1, 1),
        Keyframe("zoom", 0, 0.4), Keyframe("zoom", 1, 0.8),
    ))
    save(project, path)
    assert load(path) == project
    renderer = TimelineRenderer(640, 360)
    try:
        start = renderer.render(project, 0)
        middle = renderer.render(project, 5)
        end = renderer.render(project, 10)
        assert start[..., 1].max() == 0
        assert 100 <= middle[..., 1].max() <= 128
        assert end[..., 1].max() > 230
        assert (end[..., 1] > 50).sum() > (middle[..., 1] > 50).sum()
    finally:
        renderer.close()

    video = export_mp4(project, tmp_path / "fondu.mp4", settings=ExportSettings(height=360))
    with av.open(str(video)) as container:
        green = [frame.to_ndarray(format="rgb24")[..., 1].max()
                 for frame in container.decode(video=0)]
    assert green[0] < 10
    assert 75 < green[5] < 160
    assert green[10] > 210
