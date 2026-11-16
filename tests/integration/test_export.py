from threading import Event

import av
import numpy as np
import pytest

from makitop.export.mp4 import ExportCancelled, ExportSettings, export_mp4
from makitop.media.probe import probe
from makitop.model.project import Project
from makitop.model.timeline import ImageClip, MediaClip, Timeline


def test_export_video_trim_and_gap(tmp_path, video_file):
    media = probe(video_file)
    project = Project(timeline=Timeline(fps=10, clips=[
        MediaClip(0.1, media, 0.4, 0.7),
    ]))
    progress = []
    path = export_mp4(project, tmp_path / "montage été", progress=progress.append)
    assert path.suffix == ".mp4"
    with av.open(str(path)) as container:
        video = container.streams.video[0]
        assert video.codec_context.name == "h264"
        assert (video.width, video.height) == (1920, 1080)
        assert video.average_rate == 10
        assert container.streams.audio[0].codec_context.name == "aac"
        frames = list(container.decode(video))
        assert len(frames) == 4
        assert frames[0].to_ndarray(format="rgb24").max() < 5
        assert frames[1].to_ndarray(format="rgb24")[540, 960].mean() > 60
    with av.open(str(path)) as container:
        assert sum(f.samples for f in container.decode(audio=0)) >= 19200
    assert progress[-1] == 1


@pytest.mark.parametrize("canvas_format,size", [("9:16", (1080, 1920)), ("1:1", (1080, 1080))])
def test_export_image_format(tmp_path, image_file, canvas_format, size):
    project = Project(canvas_format=canvas_format, timeline=Timeline(clips=[
        ImageClip(0, probe(image_file), 0.1),
    ]))
    path = export_mp4(project, tmp_path / "image.mp4")
    with av.open(str(path)) as container:
        frame = next(container.decode(video=0))
        assert (frame.width, frame.height) == size
        pixel = frame.to_ndarray(format="rgb24")[size[1] // 2, size[0] // 2]
        assert pixel[0] > 240 and np.max(pixel[1:]) < 10


def test_cancel_preserves_destination(tmp_path, image_file):
    project = Project(timeline=Timeline(clips=[ImageClip(0, probe(image_file), 0.2)]))
    path = tmp_path / "existing.mp4"
    path.write_bytes(b"existing")
    cancel = Event()
    with pytest.raises(ExportCancelled):
        export_mp4(project, path, cancel=cancel, progress=lambda _: cancel.set())
    assert path.read_bytes() == b"existing"
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([path.name, image_file.name])


def test_empty_and_source_destination_rejected(tmp_path, video_file):
    with pytest.raises(ValueError, match="vide"):
        export_mp4(Project(), tmp_path / "empty.mp4")
    project = Project(timeline=Timeline(clips=[MediaClip(0, probe(video_file), 0, 0.1)]))
    original = video_file.read_bytes()
    with pytest.raises(ValueError, match="source"):
        export_mp4(project, video_file)
    assert video_file.read_bytes() == original


def test_failed_export_preserves_destination(tmp_path, image_file):
    project = Project(timeline=Timeline(clips=[ImageClip(0, probe(image_file), 0.1)]))
    image_file.unlink()
    path = tmp_path / "existing.mp4"
    path.write_bytes(b"existing")
    with pytest.raises(FileNotFoundError):
        export_mp4(project, path)
    assert path.read_bytes() == b"existing"
    assert list(tmp_path.iterdir()) == [path]


def test_audio_volume_mute_and_position(tmp_path):
    source = tmp_path / "tone.wav"
    samples = (0.5 * np.sin(2 * np.pi * 440 * np.arange(24000) / 48000)).astype(np.float32)
    with av.open(str(source), "w") as container:
        stream = container.add_stream("pcm_f32le", rate=48000)
        stream.layout = "mono"
        frame = av.AudioFrame.from_ndarray(samples[None, :], format="flt", layout="mono")
        frame.sample_rate = 48000
        container.mux(stream.encode(frame))
        container.mux(stream.encode(None))
    media = probe(source)
    project = Project(timeline=Timeline(clips=[
        MediaClip(0.1, media, 0.1, 0.3, volume=0.5),
        MediaClip(0.3, media, 0, 0.2, muted=True),
    ]))
    path = export_mp4(project, tmp_path / "audio.mp4")
    with av.open(str(path)) as container:
        decoded = np.concatenate([f.to_ndarray() for f in container.decode(audio=0)], axis=1)
    assert np.max(np.abs(decoded[:, :3500])) < 0.01
    rms = np.sqrt(np.mean(decoded[:, 6000:12000] ** 2))
    assert 0.10 < rms < 0.15
    assert np.max(np.abs(decoded[:, 17000:22000])) < 0.01


@pytest.mark.parametrize("fps", [60, 120])
def test_high_fps_export_preserves_each_source_frame(tmp_path, fps):
    source = tmp_path / "high-fps.mp4"
    with av.open(str(source), "w") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height, stream.pix_fmt = 64, 36, "yuv420p"
        for index in range(24):
            pixels = np.full((36, 64, 3), index * 10, dtype=np.uint8)
            container.mux(stream.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")))
        container.mux(stream.encode(None))
    media = probe(source)
    project = Project(timeline=Timeline(fps=30, clips=[MediaClip(0, media, 0, 24 / fps)]))
    path = export_mp4(project, tmp_path / "out.mp4", settings=ExportSettings(height=720, fps=fps))
    assert project.timeline.fps == 30  # le réglage d'export ne modifie pas le montage
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        assert stream.average_rate == fps
        assert (stream.width, stream.height) == (1280, 720)
        frames = list(container.decode(video=0))
        assert len(frames) == 24
        assert [f.time for f in frames] == pytest.approx([i / fps for i in range(24)])
        means = [f.to_ndarray(format="rgb24")[360, 640].mean() for f in frames]
        assert np.min(np.diff(means)) > 5  # aucune image intermédiaire perdue/dupliquée
    with av.open(str(path)) as container:
        audio = container.streams.audio[0]
        assert float(audio.duration * audio.time_base) == pytest.approx(24 / fps, abs=0.022)


def test_4k_export(tmp_path, image_file):
    project = Project(timeline=Timeline(clips=[ImageClip(0, probe(image_file), 1 / 60)]))
    path = export_mp4(project, tmp_path / "4k.mp4", settings=ExportSettings(height=2160, fps=60))
    with av.open(str(path)) as container:
        frame = next(container.decode(video=0))
        assert (frame.width, frame.height) == (3840, 2160)
