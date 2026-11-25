from dataclasses import replace

import av
import dearpygui.dearpygui as dpg
import numpy as np
import pytest
from PIL import Image

from makitop.application.composition import CompositionEditor
from makitop.application.projects import ProjectSession
from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.engine.audio import SAMPLE_RATE, TimelineAudioRenderer
from makitop.engine.timeline import TimelineRenderer
from makitop.engine.transitions import blend, is_available
from makitop.export.mp4 import ExportSettings, export_mp4
from makitop.media.probe import probe
from makitop.model.composition import Transform
from makitop.model.media import MediaKind
from makitop.model.project import Project
from makitop.model.timeline import ImageClip, MediaClip, TextClip, Timeline
from makitop.model.transitions import CATALOG, Transition
from makitop.storage.project_file import load, save
from makitop.storage.recent import RecentProjects
from makitop.ui import main_window
from makitop.ui.panels import properties, sidebar, timeline, transitions


@pytest.mark.parametrize("kind", CATALOG)
def test_catalog_preset_produces_a_thumbnail_and_preserves_endpoints(kind):
    if not is_available(kind):
        pytest.skip("Préréglage absent de cette version de FFmpeg.")
    assert np.isfinite(transitions.thumbnail(kind)).all()
    a = np.full((24, 32, 4), (255, 0, 0, 255), np.uint8)
    b = np.full_like(a, 255)
    b[..., :3] = (0, 0, 255)
    a[4:16, 2:10, :3] = (45, 155, 180)
    b[8:19, 18:25, :3] = (50, 145, 170)
    np.testing.assert_array_equal(blend(a, b, kind, 0), a)
    np.testing.assert_array_equal(blend(a, b, kind, 1), b)
    phases = [blend(a, b, kind, p) for p in (0.2, 0.45, 0.7)]
    assert all(frame.shape == a.shape and frame.dtype == np.uint8 for frame in phases)
    assert any(not np.array_equal(frame, a) and not np.array_equal(frame, b)
               for frame in phases)


def _image(tmp_path, name, color):
    path = tmp_path / name
    Image.new("RGB", (64, 36), color).save(path)
    return probe(path)


def test_transition_catalog_applies_edits_and_removes_a_transition(tmp_path, monkeypatch):
    dpg.create_context()
    playback = TimelinePlaybackController()
    editor = CompositionEditor(ProjectSession(RecentProjects(tmp_path / "recent.json")), playback)
    errors = []
    monkeypatch.setattr(dpg, "get_text_size", lambda text: (len(text) * 8, 16))
    try:
        main_window.build()
        properties.bind(editor, errors.append)
        timeline.bind(editor, errors.append)
        transitions.bind(properties.apply_transition)
        editor.on_refresh = lambda: (properties.refresh(), timeline.refresh())
        assert not dpg.does_item_exist(transitions.FILTER)
        sidebar.select("transitions")
        assert dpg.does_item_exist(transitions.FILTER)
        assert sum(dpg.does_item_exist(transitions.button_tag(kind)) for kind in CATALOG) == sum(
            is_available(kind) for kind in CATALOG
        )

        a = editor.add_media(_image(tmp_path, "red.png", "red"), 0)
        b = editor.add_media(_image(tmp_path, "blue.png", "blue"), a.timeline_end)
        dpg.get_item_callback(transitions.button_tag("fade"))(None, None, "fade")
        assert editor.selected_transition == Transition(a.id, b.id, "fade")
        assert editor.project.timeline.duration == 10
        assert dpg.get_value(properties.TABS) == properties.TAB_TRANSITION
        assert dpg.does_item_exist(f"timeline_transition_{b.id}")
        dpg.get_item_callback("clip_transition_duration")(None, 0.4)
        assert editor.selected_transition.duration == pytest.approx(0.4)
        assert dpg.get_value("clip_transition_info").startswith("Durée utilisée : 0.40 s")
        dpg.get_item_callback("clip_transition_remove")()
        assert not editor.project.timeline.transitions
        assert not dpg.is_item_shown(properties.TAB_TRANSITION)
        assert not dpg.does_item_exist(f"timeline_transition_{b.id}")
        timeline.undo()
        assert editor.selected_transition.duration == pytest.approx(0.4)
        assert dpg.does_item_exist(f"timeline_transition_{b.id}")
        timeline.undo()
        assert editor.selected_transition.duration == pytest.approx(0.8)
        timeline.undo()
        assert not editor.project.timeline.transitions
        timeline.redo()
        assert editor.selected_transition == Transition(a.id, b.id, "fade")
        timeline.redo()
        timeline.redo()
        assert not editor.project.timeline.transitions
        assert not dpg.does_item_exist(f"timeline_transition_{b.id}")
        editor.update_clip(b.id, timeline_start=6)
        dpg.get_item_callback(transitions.button_tag("fade"))(None, None, "fade")
        assert errors and not editor.project.timeline.transitions
    finally:
        transitions.bind(None)
        playback.close()
        dpg.destroy_context()


def test_round_trip_and_export_use_same_transition_without_moving_cuts(tmp_path):
    red = _image(tmp_path, "red.png", "red")
    blue = _image(tmp_path, "blue.png", "blue")
    a, b = ImageClip(0, red, 0.5), ImageClip(0.5, blue, 0.5, track=1)
    transition = Transition(a.id, b.id, "fade", 0.4)
    project = Project(media=[red, blue],
                      timeline=Timeline([a, b], fps=10, transitions=(transition,)))
    path = tmp_path / "transition.makitop"
    save(project, path)
    project = load(path)
    assert project.timeline.transitions == (transition,)
    assert project.timeline.duration == 1
    renderer = TimelineRenderer(64, 36)
    try:
        # Rendu dans le désordre, comme un seek dans le lecteur.
        assert renderer.render(project, 9)[18, 32].tolist() == [0, 0, 255]
        assert renderer.render(project, 5)[18, 32].tolist() == [128, 0, 128]
        assert renderer.render(project, 2)[18, 32].tolist() == [255, 0, 0]
    finally:
        renderer.close()
    result = export_mp4(project, tmp_path / "transition.mp4", settings=ExportSettings(height=360))
    with av.open(str(result)) as container:
        frames = [frame.to_ndarray(format="rgb24")[180, 320] for frame in container.decode(video=0)]
    assert len(frames) == 10
    assert frames[5] == pytest.approx([128, 0, 128], abs=6)
    project.timeline.remove_clip(a.id)
    assert not project.timeline.transitions


def test_overlap_switches_to_incoming_even_if_outgoing_is_higher(tmp_path):
    red = _image(tmp_path, "red.png", "red")
    blue = _image(tmp_path, "blue.png", "blue")
    a, b = ImageClip(0, red, 3, track=2), ImageClip(1, blue, 4, track=0)
    timeline_model = Timeline([a, b], fps=10, transitions=(Transition(a.id, b.id, "fade", 0.4),))
    renderer = TimelineRenderer(64, 36)
    try:
        frame = renderer.render(Project(timeline=timeline_model), 15)
        assert frame[18, 32].tolist() == [0, 0, 255]
    finally:
        renderer.close()


def test_transition_preserves_text_overlay_and_handles_rotated_stretched_layer(tmp_path):
    red = _image(tmp_path, "red.png", "red")
    blue = _image(tmp_path, "blue.png", "blue")
    a = ImageClip(0, red, 1, transform=Transform(rotation=90, stretch=True))
    b = ImageClip(1, blue, 1)
    title = TextClip(0, 2, "Titre", track=3)
    model = Timeline([a, b, title], fps=10, transitions=(Transition(a.id, b.id, "fade"),))
    renderer = TimelineRenderer(320, 180)
    try:
        frame = renderer.render(Project(timeline=model), 10)
        assert (frame[..., 1] > 180).any()  # Le titre blanc reste visible.
        assert frame[25, 160] == pytest.approx([128, 0, 128], abs=1)
        assert frame[25, 30] == pytest.approx([0, 0, 128], abs=1)
    finally:
        renderer.close()


@pytest.mark.parametrize("speed", [1.0, 2.0])
def test_audio_crossfade_blends_source_handles(tmp_path, speed):
    path = tmp_path / "stereo.wav"
    signal = np.zeros((2, SAMPLE_RATE * 2), dtype=np.float32)
    signal[0, :SAMPLE_RATE] = 0.5
    signal[1, SAMPLE_RATE:] = 0.5
    with av.open(str(path), "w") as container:
        stream = container.add_stream("pcm_f32le", rate=SAMPLE_RATE)
        stream.layout = "stereo"
        frame = av.AudioFrame.from_ndarray(signal, format="fltp", layout="stereo")
        frame.sample_rate = SAMPLE_RATE
        container.mux(stream.encode(frame))
        container.mux(stream.encode(None))
    media = replace(probe(path), kind=MediaKind.VIDEO)
    a = MediaClip(0, media, 0.2, 0.7, speed=speed)
    b = MediaClip(a.timeline_end, media, 1.3, 1.8, speed=speed)
    project = Project(timeline=Timeline(
        [a, b], transitions=(Transition(a.id, b.id, "fade", 0.4 / speed),),
    ))
    renderer = TimelineAudioRenderer()
    try:
        signal = renderer.render(project, 0, SAMPLE_RATE)
        assert signal[int(0.2 * SAMPLE_RATE / speed)] == pytest.approx([0.5, 0])
        assert signal[int(0.5 * SAMPLE_RATE / speed)] == pytest.approx([0.25, 0.25])
        assert signal[int(0.8 * SAMPLE_RATE / speed)] == pytest.approx([0, 0.5])
    finally:
        renderer.close()
