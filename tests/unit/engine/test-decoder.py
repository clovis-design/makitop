from makitop.engine.decoder import MediaDecoder

from makitop.engine.render import Renderer


decoder = MediaDecoder()
decoder.open("test.mp4")

renderer = Renderer(decoder)

frame = renderer.render(0)

print(frame.shape)
