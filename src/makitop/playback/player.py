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

        # On replace aussi le décodeur au début de la vidéo
        self.renderer.decoder.seek(0.0)

    def seek(self, position: float) -> None:
        # Déplace l'horloge
        self.clock.seek(position)

        # Déplace aussi PyAV
        self.renderer.decoder.seek(position)

    def current_time(self) -> float:
        return self.clock.current_time()

    def current_frame(self):
        """
        Demande une frame précise correspondant au temps courant.

        Utile après un seek ou lorsque la vidéo est arrêtée.
        """
        time = self.current_time()

        return self.renderer.render(time)

    def next_frame(self):
        """
        Retourne la prochaine frame pendant Play.
        """
        return self.renderer.next_frame()

    def is_playing(self) -> bool:
        return self.clock.playing