class Renderer:
    def __init__(self, decoder):
        self.decoder = decoder

    def render(self, time: float):
        """
        Demande une frame précise à un instant donné.

        À utiliser pour :
        - un seek
        - un slider
        - un clic dans la timeline
        """
        return self.decoder.get_frame_at(time)

    def next_frame(self):
        """
        Récupère simplement la prochaine frame pendant Play.
        On ne fait PAS de seek ici.
        """
        frame = self.decoder.next_frame()

        if frame is None:
            return None

        if frame.time is None:
            return None

        image = frame.to_ndarray(format="rgb24")

        return image, frame.time