from dataclasses import replace
from fractions import Fraction

import av
import numpy as np
import pytest

from makitop.engine.audio import SAMPLE_RATE, AudioDecoder, TimelineAudioRenderer
from makitop.media.probe import probe
from makitop.model.project import Project
from makitop.model.timeline import MediaClip, Timeline


@pytest.fixture
def signal_file(tmp_path):
    path = tmp_path / "signal.mkv"
    rate = 44100
    with av.open(str(path), "w") as container:
        video = container.add_stream("mpeg4", rate=10)
        video.width, video.height, video.pix_fmt = 64, 48, "yuv420p"
        stream = container.add_stream("pcm_f32le", rate=rate)
        stream.layout = "stereo"
        for _ in range(10):
            pixels = np.zeros((48, 64, 3), dtype=np.uint8)
            container.mux(video.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")))
        container.mux(video.encode())
        samples = np.zeros((2, rate), dtype=np.float32)
        samples[0, :rate // 2] = 0.25
        samples[1, rate // 2:] = -0.5
        frame = av.AudioFrame.from_ndarray(samples, format="fltp", layout="stereo")
        frame.sample_rate = rate
        frame.time_base = Fraction(1, rate)
        frame.pts = 0
        container.mux(stream.encode(frame))
        container.mux(stream.encode())
    return path


def test_resampling_channels_sequential_read_and_backward_seek(signal_file):
    decoder = AudioDecoder(signal_file)
    try:
        first = decoder.read(4800, 2048)
        assert first.shape == (2048, 2)
        assert first.dtype == np.float32
        np.testing.assert_allclose(first[:, 0], 0.25, atol=1e-5)
        np.testing.assert_allclose(first[:, 1], 0, atol=1e-5)
        np.testing.assert_allclose(decoder.read(6848, 2048), first, atol=1e-5)
        later = decoder.read(30000, 2048)
        np.testing.assert_allclose(later[:, 1], -0.5, atol=1e-5)
        np.testing.assert_allclose(later[:, 0], 0, atol=1e-5)
        np.testing.assert_allclose(decoder.read(4800, 2048), first, atol=1e-5)
        assert not decoder.read(2 * SAMPLE_RATE, 2048).any()
    finally:
        decoder.close()


def test_montage_cuts_gaps_and_end(signal_file):
    media = probe(signal_file)
    project = Project(media=[media], timeline=Timeline(clips=[
        MediaClip(timeline_start=0.1, media=media, source_start=0.2, source_end=0.3),
        MediaClip(timeline_start=0.2, media=media, source_start=0.6, source_end=0.7),
    ]))
    renderer = TimelineAudioRenderer()
    try:
        samples = renderer.render(project, 0, SAMPLE_RATE // 2)
        assert not samples[:4800].any()
        np.testing.assert_allclose(samples[4800:9600, 0], 0.25, atol=1e-5)
        np.testing.assert_allclose(samples[4800:9600, 1], 0, atol=1e-5)
        np.testing.assert_allclose(samples[9600:14400, 1], -0.5, atol=1e-5)
        np.testing.assert_allclose(samples[9600:14400, 0], 0, atol=1e-5)
        assert not samples[14400:].any()
    finally:
        renderer.close()


def test_video_without_audio_is_silent(video_file):
    media = probe(video_file)
    media = replace(media, audio_codec=None)
    project = Project(timeline=Timeline(clips=[MediaClip(0, media, 0, 1)]))
    renderer = TimelineAudioRenderer()
    try:
        assert not renderer.render(project, 0, 2048).any()
        assert renderer.decoder is None
    finally:
        renderer.close()


def test_mix_tracks_volume_mute_and_independent_source_times(signal_file):
    media = probe(signal_file)
    a = MediaClip(0, media, 0.1, 0.3, volume=0.5)
    b = MediaClip(0, media, 0.6, 0.8, volume=0.25, track=1)
    project = Project(timeline=Timeline(clips=[a, b]))
    renderer = TimelineAudioRenderer()
    try:
        samples = renderer.render(project, 0, 1024)
        np.testing.assert_allclose(samples[:, 0], 0.125, atol=1e-5)
        np.testing.assert_allclose(samples[:, 1], -0.125, atol=1e-5)
        b.muted = True
        samples = renderer.render(project, 1024, 1024)
        np.testing.assert_allclose(samples[:, 0], 0.125, atol=1e-5)
        assert not samples[:, 1].any()
        assert b.id not in renderer.decoders
        a.volume = 0
        assert not renderer.render(project, 2048, 1024).any()
    finally:
        renderer.close()


def test_mix_is_limited_to_output_range(signal_file):
    media = probe(signal_file)
    project = Project(timeline=Timeline(clips=[
        MediaClip(0, media, 0.1, 0.3, volume=2, track=i) for i in range(3)
    ]))
    renderer = TimelineAudioRenderer()
    try:
        samples = renderer.render(project, 0, 1024)
        assert samples.max() == 1
        assert not samples[:, 1].any()
    finally:
        renderer.close()
