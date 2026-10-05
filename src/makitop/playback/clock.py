import time


class PlaybackClock:
    def __init__(self) -> None:
        self.position = 0.0
        self.started_at = None
        self.playing = False

    def play(self) -> None:
        if self.playing:
            return

        self.started_at = time.perf_counter()
        self.playing = True

    def pause(self) -> None:
        if not self.playing:
            return

        elapsed = time.perf_counter() - self.started_at

        self.position += elapsed

        self.started_at = None
        self.playing = False

    def stop(self) -> None:
        self.position = 0.0
        self.started_at = None
        self.playing = False

    def seek(self, position: float) -> None:
        self.position = position

        if self.playing:
            self.started_at = time.perf_counter()

    def current_time(self) -> float:
        if not self.playing:
            return self.position

        elapsed = time.perf_counter() - self.started_at

        return self.position + elapsed