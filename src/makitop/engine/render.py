

class Renderer:

    def __init__(self, decoder):
        self.decoder = decoder


    def render(self, time: float):
        return self.decoder.get_frame_at(time)
    

    def get_frame_at(self, target_time: float):
        self.container.seek(0)

        for frame in self.container.decode(video=0):

            if frame.time is None:
                continue

            if frame.time >= target_time:
                return frame.to_ndarray(format="rgb24")

        return None