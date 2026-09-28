

class Renderer:

    def __init__(self, decoder):
        self.decoder = decoder

    def render(self, time):
        return self.decoder.get_first_frame()