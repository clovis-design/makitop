"""Lecture non bloquante : horloge montage et préchargement sur un worker unique."""

import math
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from makitop.engine.timeline import TimelineRenderer
from makitop.playback.clock import PlaybackClock


class TimelinePlaybackController:
    def __init__(self, renderer=None):
        self.renderer = renderer or TimelineRenderer()
        self.clock = PlaybackClock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="timeline")
        self.project = None
        self.pending = {}
        self.displayed = None

    @property
    def duration(self):
        return self.project.timeline.duration if self.project else 0.0

    def _discard(self):
        for future in self.pending.values():
            future.cancel()
        self.pending.clear()
        self.displayed = None

    def set_project(self, project, position=0.0):
        self.clock.stop()
        self._discard()
        # Le worker ne doit jamais observer une timeline en cours de modification.
        self.project = deepcopy(project)
        self.seek(position)

    def play(self):
        if self.duration > 0:
            if self.current_time() >= self.duration:
                self.seek(0)
            self.clock.play()

    def pause(self):
        self.clock.pause()

    def stop(self):
        self.clock.stop()
        self._discard()

    def seek(self, position):
        if not math.isfinite(position):
            raise ValueError("Position invalide.")
        self.clock.seek(max(0.0, min(position, self.duration)))
        self._discard()

    def current_time(self):
        return min(self.clock.current_time(), self.duration)

    def is_playing(self):
        return self.clock.playing

    def poll(self):
        """Renvoie seulement l'image due, jamais une image anticipée ou obsolète."""
        if self.project is None:
            return None
        fps = self.project.timeline.fps
        if self.clock.playing and self.clock.current_time() >= self.duration:
            self.clock.pause()
            self.clock.seek(self.duration)
        last = max(0, math.ceil(self.duration * fps - 1e-9) - 1)
        index = min(int(self.current_time() * fps), last)
        wanted = range(index, min(last + 1, index + (8 if self.is_playing() else 1)))
        for target in wanted:
            if target not in self.pending:
                self.pending[target] = self.executor.submit(
                    self.renderer.render, self.project, target
                )
        # Si le décodage est lent, afficher le dernier résultat dû plutôt que
        # jeter chaque image en retard et rester indéfiniment sur la première.
        ready = [i for i, f in self.pending.items() if i <= index and f.done()
                 and not f.cancelled() and (self.displayed is None or i > self.displayed)]
        rendered = max(ready) if ready else None
        future = self.pending[rendered] if rendered is not None else None
        for old in list(self.pending):
            task = self.pending[old]
            if old not in wanted and not task.running():
                task.cancel()
                del self.pending[old]
        if future is not None:
            try:
                image = future.result()
            except Exception:
                self.pause()
                self._discard()
                self.displayed = index
                raise
            self.displayed = rendered
            return image
        return None

    def close(self):
        self.clock.stop()
        self._discard()
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.renderer.close()
