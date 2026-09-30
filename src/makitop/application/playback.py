from makitop.playback.player import Player


class PlaybackController:
    def __init__(self, player) -> None:
        self.player = player    

    def play(self) -> None:
        print("PLAY")
        self.player.play()

    def pause(self) -> None:
        self.player.pause()

    def stop(self) -> None:
        self.player.stop()

    def seek(self, position: float) -> None:
        self.player.seek(position)

    def current_time(self) -> float:
        return self.player.current_time()

    def current_frame(self):
        return self.player.current_frame()