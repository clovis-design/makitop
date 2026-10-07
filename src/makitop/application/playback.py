from pathlib import Path

from makitop.engine.decoder import MediaDecoder
from makitop.engine.render import Renderer
from makitop.playback.player import Player


class PlaybackController:
    def __init__(self, player: Player | None = None) -> None:
        self.player = player
        self.decoder: MediaDecoder | None = None

    def load(self, path: Path):
        """Charge une vidéo à l'arrêt ; conserve la précédente en cas d'échec."""

        decoder = MediaDecoder()

        try:
            decoder.open(path)

            frame = decoder.get_first_frame()

            if frame is None:
                raise ValueError(
                    "La vidéo ne contient aucune image lisible."
                )

            duration = decoder.get_duration()

        except Exception:
            decoder.close()
            raise

        # On ferme l'ancienne vidéo seulement si
        # la nouvelle vidéo a bien été chargée.
        self.close()

        self.decoder = decoder
        self.player = Player(
            Renderer(decoder)
        )

        return frame, duration

    def close(self) -> None:
        if self.player is not None:
            self.player.stop()

        if self.decoder is not None:
            self.decoder.close()

        self.player = None
        self.decoder = None

    def play(self) -> None:
        if self.player is not None:
            self.player.play()

    def pause(self) -> None:
        if self.player is not None:
            self.player.pause()

    def stop(self) -> None:
        if self.player is not None:
            self.player.stop()

    def seek(self, position: float) -> None:
        if self.player is not None:
            self.player.seek(position)

    def current_time(self) -> float:
        if self.player is None:
            return 0.0

        return self.player.current_time()

    def current_frame(self):
        if self.player is None:
            return None

        return self.player.current_frame()

    def next_frame(self):
        if self.player is None:
            return None

        return self.player.next_frame()

    def is_playing(self) -> bool:
        if self.player is None:
            return False

        return self.player.is_playing()