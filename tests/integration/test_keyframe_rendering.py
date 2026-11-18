"""Animations réellement rendues, mixées et encodées."""

import json
from dataclasses import replace

import av
import numpy as np
import pytest

from makitop.engine.audio import SAMPLE_RATE, TimelineAudioRenderer
from makitop.engine.timeline import TimelineRenderer
from makitop.export.mp4 import ExportSettings, export_mp4
from makitop.media.probe import probe
from makitop.model.composition import Transform
from makitop.model.keyframes import Keyframe
from makitop.model.project import Project
from makitop.model.timeline import ImageClip, MediaClip, Timeline
from makitop.storage.project_file import ProjectFileError, load, save


def animated_project(image_file):
    media = probe(image_file)
    clip = ImageClip(0, media, 1, transform=Transform(width=0.25, height=0.25), keyframes=(
        Keyframe("x", 0, 0), Keyframe("x", 0.5, 0.75),
        Keyframe("width", 0, 0.25), Keyframe("width", 0.5, 0.5),
    ))
    return Project(media=[media], timeline=Timeline(clips=[clip], fps=60))


def test_animated_image_cache_and_export_agree(tmp_path, image_file):
    project = animated_project(image_file)
    renderer = TimelineRenderer(1280, 720)
    try:
        start = renderer.render(project, 0)
        middle = renderer.render(project, 15)
        end = renderer.render(project, 30)
        assert not np.array_equal(start, middle)
        assert not np.array_equal(middle, end)
        assert start[:, :320].sum() > 0 and start[:, 400:].sum() == 0
        assert end[:, :900].sum() == 0 and end[:, 1000:].sum() > 0
        path = export_mp4(project, tmp_path / "animated.mp4",
                          settings=ExportSettings(height=720, fps=60))
        with av.open(str(path)) as container:
            frames = list(container.decode(video=0))
        assert len(frames) == 60
        for index, expected in [(0, start), (15, middle), (30, end)]:
            actual = frames[index].to_ndarray(format="rgb24")
            assert np.abs(actual.astype(float) - expected).mean() < 2
    finally:
        renderer.close()


@pytest.mark.parametrize("mode", ["linear", "smooth", "constant"])
def test_audio_envelope_is_sample_accurate_and_block_independent(tmp_path, mode):
    path = tmp_path / "tone.wav"
    with av.open(str(path), "w") as out:
        stream = out.add_stream("pcm_f32le", rate=SAMPLE_RATE)
        stream.layout = "stereo"
        samples = np.full((1, SAMPLE_RATE), 0.25, dtype=np.float32)
        frame = av.AudioFrame.from_ndarray(samples, format="flt", layout="stereo")
        frame.sample_rate = SAMPLE_RATE
        out.mux(stream.encode(frame))
        out.mux(stream.encode(None))
    media = probe(path)
    clip = MediaClip(0.1, media, 0, 0.5, volume=0, keyframes=(
        Keyframe("volume", 0, 0, mode), Keyframe("volume", 0.4, 1),
    ))
    project = Project(timeline=Timeline(clips=[clip]))
    renderer = TimelineAudioRenderer()
    other = TimelineAudioRenderer()
    try:
        result = renderer.render(project, 0, 28800)
        chunks = np.concatenate([other.render(project, i, min(731, 28800 - i))
                                 for i in range(0, 28800, 731)])
        np.testing.assert_allclose(result, chunks, atol=1e-7)
        for time in (0.1, 0.2, 0.3, 0.4, 0.5):
            index = round((0.1 + time) * SAMPLE_RATE)
            if index < len(result):
                assert result[index, 0] == pytest.approx(0.25 * clip.volume_at(time), abs=1e-6)
        assert not result[:4800].any()
    finally:
        renderer.close()
        other.close()


def test_keyframe_project_round_trip_and_legacy(tmp_path, image_file):
    project = animated_project(image_file)
    path = tmp_path / "animation.makitop"
    save(project, path)
    assert load(path) == project
    data = json.loads(path.read_text())
    data["timeline"][0]["keyframes"][0]["value"] = float("nan")
    path.write_text(json.dumps(data))
    with pytest.raises(ProjectFileError, match="corrompu"):
        load(path)
    del data["timeline"][0]["keyframes"]
    data["version"] = 4
    path.write_text(json.dumps(data))
    legacy = load(path)
    assert legacy.timeline.clips[0] == replace(project.timeline.clips[0], keyframes=())
