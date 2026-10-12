from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.model.media import Media, MediaKind
from makitop.model.project import Project
from makitop.model.timeline import MediaClip, Timeline
from makitop.playback.audio import AudioPlayer


def project():
    media = Media(Path("video.mp4"), MediaKind.VIDEO, duration=1, audio_codec="aac")
    return Project(timeline=Timeline(clips=[MediaClip(0, media, 0, 1)]))


def test_output_sync_latency_stop_and_cleanup():
    started = Event()
    closed = Event()
    callbacks = []

    class Renderer:
        def render(self, project, start, count):
            return np.repeat(np.arange(start, start + count)[:, None], 2, axis=1)

        def close(self):
            closed.set()

    class Stream:
        def __init__(self, **kwargs):
            assert kwargs["samplerate"] == 48000
            callbacks.append(kwargs["callback"])

        def start(self):
            started.set()

        def abort(self):
            pass

        def close(self):
            pass

    clock = SimpleNamespace(playing=True, current_time=lambda: 0.1)
    player = AudioPlayer(Renderer, Stream)
    try:
        player.start(project(), clock)
        assert started.wait(3)
        output = np.zeros((2048, 2), dtype=np.float32)
        timing = SimpleNamespace(outputBufferDacTime=1.02, currentTime=1)
        callbacks[0](output, 2048, timing, None)
        np.testing.assert_array_equal(output[:, 0], np.arange(5760, 7808))
        player.stop()
        assert closed.is_set()
        callbacks[0](output, 2048, timing, None)
        assert not output.any()
    finally:
        player.close()


def test_unavailable_device_reports_error_once():
    class Renderer:
        def render(self, project, start, count):
            return np.zeros((count, 2), dtype=np.float32)

        def close(self):
            pass

    def unavailable(**kwargs):
        raise RuntimeError("aucun périphérique")

    player = AudioPlayer(Renderer, unavailable)
    try:
        player.start(project(), SimpleNamespace(playing=True, current_time=lambda: 0))
        player.thread.join(timeout=3)
        assert not player.thread.is_alive()
        with pytest.raises(RuntimeError, match="aucun périphérique"):
            player.check_error()
        player.check_error()
    finally:
        player.close()


def test_silent_video_does_not_open_audio_device():
    silent = project()
    silent.timeline.clips[0].media = replace(silent.timeline.clips[0].media, audio_codec=None)

    def unexpected(**kwargs):
        raise AssertionError("Aucune sortie audio nécessaire")

    player = AudioPlayer(stream_factory=unexpected)
    try:
        player.start(silent, SimpleNamespace(playing=True, current_time=lambda: 0))
        assert player.thread is None
        player.check_error()
    finally:
        player.close()


def test_controller_audio_transport(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("makitop.playback.clock.time.perf_counter", lambda: now[0])
    calls = []

    class Audio:
        def start(self, project, clock):
            calls.append(("start", clock.current_time()))

        def stop(self):
            calls.append("stop")

        def close(self):
            calls.append("close")

        def check_error(self):
            pass

    class Renderer:
        def render(self, project, index):
            return np.array([index])

        def close(self):
            pass

    controller = TimelinePlaybackController(Renderer(), Audio())
    try:
        controller.set_project(project())
        controller.play()
        assert calls[-1] == ("start", 0)
        count = len(calls)
        controller.play()
        assert len(calls) == count
        now[0] = 0.2
        controller.pause()
        assert calls[-1] == "stop"
        controller.play()
        assert calls[-1] == ("start", 0.2)
        controller.seek(0.6)
        assert calls[-2:] == ["stop", ("start", 0.6)]
        controller.stop()
        assert calls[-1] == "stop"
        assert controller.current_time() == 0
        controller.play()
        now[0] = 2
        controller.poll()
        assert calls[-1] == "stop"
        assert not controller.is_playing()
        controller.play()
        assert calls[-1] == ("start", 0)
        controller.set_project(project())
        assert calls[-1] == "stop"
        assert not controller.is_playing()
    finally:
        controller.close()
    assert calls[-1] == "close"
