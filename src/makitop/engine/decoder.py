import av


class MediaDecoder:
    def __init__(self):
        self.container = None
        self.video_stream = None
        self.frame_iterator = None
        self._sample = None
        self._ahead = None
        self._sample_time = None

    def open(self, path):
        self.container = av.open(str(path))
        self.video_stream = self.container.streams.video[0]

        # Prépare la lecture séquentielle des frames
        self._reset_frame_iterator()

    def close(self):
        if self.container is not None:
            self.container.close()

        self.container = None
        self.video_stream = None
        self.frame_iterator = None

    def _reset_frame_iterator(self):
        """
        Crée un nouvel itérateur permettant de lire
        les frames les unes après les autres.
        """
        self.frame_iterator = self.container.decode(video=0)
        self._sample = None
        self._ahead = None
        self._sample_time = None

    def sample_at(self, target_time):
        """Image couvrant ce temps ; décodage séquentiel entre deux seeks.

        L'image précédant la cible est conservée jusqu'au timestamp suivant,
        y compris lorsque la cadence source diffère de celle du montage.
        """
        if (self._sample_time is None or target_time < self._sample_time
                or target_time - self._sample_time > 1):
            self.seek(target_time)
        while True:
            if self._ahead is None:
                self._ahead = self.next_frame()
            if self._ahead is None:
                break
            if self._ahead.time is None:
                self._ahead = None
                continue
            if self._ahead.time > target_time + 1e-9:
                break
            self._sample = self._ahead
            self._ahead = None
        self._sample_time = target_time
        frame = self._sample if self._sample is not None else self._ahead
        return None if frame is None else frame.to_ndarray(format="rgb24")

    def get_info(self):
        return {
            "width": self.video_stream.width,
            "height": self.video_stream.height,
            "fps": float(self.video_stream.average_rate),
            "codec": self.video_stream.codec_context.name,
        }

    def get_first_frame(self):
        # Retour au début
        self.container.seek(0)

        # Comme on change de position dans la vidéo,
        # on recrée l'itérateur
        self._reset_frame_iterator()

        frame = next(self.frame_iterator, None)

        if frame is None:
            return None

        return frame.to_ndarray(format="rgb24")

    def next_frame(self):
        """
        Retourne la prochaine frame PyAV.

        Cette méthode est utilisée pendant la lecture normale
        pour éviter de repartir du début à chaque image.
        """
        if self.frame_iterator is None:
            return None

        frame = next(self.frame_iterator, None)

        return frame

    def seek(self, target_time: float):
        """
        Déplace le décodeur vers une position de la vidéo.

        target_time est exprimé en secondes.
        """

        if self.container is None or self.video_stream is None:
            return

        # PyAV utilise la time_base du stream et non directement
        # des secondes.
        timestamp = int(
            target_time / float(self.video_stream.time_base)
        )

        self.container.seek(
            timestamp,
            stream=self.video_stream,
            backward=True,
        )

        # Après un seek, il faut recréer l'itérateur
        self._reset_frame_iterator()

    def get_frame_at(self, target_time: float):
        """
        Recherche une frame précise dans la vidéo.

        Cette méthode sera utilisée pour :
        - le slider
        - le clic dans la timeline
        - le seek

        Elle ne doit PAS être appelée à chaque frame pendant Play.
        """

        self.seek(target_time)

        while True:
            frame = self.next_frame()

            if frame is None:
                return None

            if frame.time is None:
                continue

            if frame.time >= target_time:
                return frame.to_ndarray(format="rgb24")

    def get_duration(self) -> float:
        if self.container is None:
            return 0.0

        if self.container.duration is None:
            return 0.0

        return self.container.duration / 1_000_000
