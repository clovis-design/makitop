import av

from pathlib import Path



class MediaDecoder:

    def __init__(self):
        self.container = None
        self.video_stream = None

    def open(self, path):
        self.container = av.open(str(Path(path)))
        self.video_stream = self.container.streams.video[0]

    def get_info(self):
        return {
            "width": self.video_stream.width,
            "height": self.video_stream.height,
            "fps": float(self.video_stream.average_rate),
        }

    def get_first_frame(self):

        for frame in self.container.decode(video=0):
            image = frame.to_ndarray(format="rgb24")

            return image