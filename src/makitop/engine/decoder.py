import av


class MediaDecoder:
    def __init__(self):
        self.container = None
        self.video_stream = None

    def open(self, path):
        self.container = av.open(str(path))
        self.video_stream = self.container.streams.video[0]

    def get_info(self):
        return {
            "width": self.video_stream.width,
            "height": self.video_stream.height,
            "fps": float(self.video_stream.average_rate),
            "codec": self.video_stream.codec_context.name,
        }

    def get_first_frame(self):
        for frame in self.container.decode(video=0):
            return frame.to_ndarray(format="rgb24")

        return None

    def get_frame_at(self, target_time: float):
        # On revient au début de la vidéo
        self.container.seek(0)

        # On décode les frames une par une
        for frame in self.container.decode(video=0):

            # Certaines frames peuvent ne pas avoir de timestamp
            if frame.time is None:
                continue

            # Dès qu'on atteint le temps demandé,
            # on retourne l'image sous forme de tableau NumPy
            if frame.time >= target_time:
                return frame.to_ndarray(format="rgb24")

        # Si aucune frame n'est trouvée
        return None

    def get_duration(self) -> float:
        if self.container.duration is None:
            return 0.0

        return self.container.duration / 1_000_000