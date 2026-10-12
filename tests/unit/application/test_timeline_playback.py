import time
from threading import Event

import numpy as np

from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.model.project import Project
from makitop.model.timeline import Clip, Timeline


class Renderer:
    def render(self, project, index):
        return np.array([index])

    def close(self):
        pass


def wait_frame(controller):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        frame = controller.poll()
        if frame is not None:
            return frame
        time.sleep(0.001)
    raise AssertionError("Aucune image reçue")


def project():
    return Project(timeline=Timeline([Clip("source", 0, 1, 0)], fps=10))


def test_clock_controls_frames_not_ui_iterations(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("makitop.playback.clock.time.perf_counter", lambda: now[0])
    controller = TimelinePlaybackController(Renderer())
    try:
        controller.set_project(project())
        assert wait_frame(controller)[0] == 0
        controller.play()
        for _ in range(50):
            assert controller.poll() is None
        now[0] = 0.35
        assert wait_frame(controller)[0] == 3
        controller.pause()
        now[0] = 10
        assert controller.current_time() == 0.35
        controller.seek(0.7)
        assert wait_frame(controller)[0] == 7
        controller.stop()
        assert wait_frame(controller)[0] == 0
        controller.play()
        now[0] = 12
        assert wait_frame(controller)[0] == 9
        assert not controller.is_playing()
        assert controller.current_time() == 1
    finally:
        controller.close()


def test_seek_discards_in_flight_result():
    entered, release = Event(), Event()

    class SlowRenderer(Renderer):
        def render(self, project, index):
            if index == 0:
                entered.set()
                assert release.wait(3)
            return super().render(project, index)

    controller = TimelinePlaybackController(SlowRenderer())
    try:
        original = project()
        controller.set_project(original)
        assert controller.poll() is None
        assert entered.wait(3)
        original.timeline.clips.clear()
        assert controller.duration == 1  # instantané indépendant du modèle UI
        controller.seek(0.8)
        release.set()
        assert wait_frame(controller)[0] == 8
    finally:
        release.set()
        controller.close()


def test_slow_frame_is_not_discarded_forever(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("makitop.playback.clock.time.perf_counter", lambda: now[0])
    entered, release = Event(), Event()

    class SlowRenderer(Renderer):
        def render(self, project, index):
            entered.set()
            assert release.wait(3)
            return super().render(project, index)

    controller = TimelinePlaybackController(SlowRenderer())
    try:
        controller.set_project(project())
        controller.play()
        controller.poll()
        assert entered.wait(3)
        now[0] = 0.35
        controller.poll()
        release.set()
        # Le résultat prêt doit être dû (<= 3), jamais une image future.
        assert wait_frame(controller)[0] <= 3
    finally:
        release.set()
        controller.close()
