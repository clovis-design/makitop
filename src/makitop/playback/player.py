from makitop.playback.clock import PlaybackClock


class Player:
    def __init__(self, renderer) -> None:
        self.clock = PlaybackClock()
        self.renderer = renderer

    def play(self) -> None:
        self.clock.play()

    def pause(self) -> None:
        self.clock.pause()

    def stop(self) -> None:
        self.clock.stop()

    def seek(self, position: float) -> None:
        self.clock.seek(position)

    def current_time(self) -> float:
        return self.clock.current_time()

    def current_frame(self):
        time = self.current_time()

        return self.renderer.render(time)