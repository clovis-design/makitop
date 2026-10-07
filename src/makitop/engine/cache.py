"""Cache LRU d'images rendues, borné en octets ; réservé au worker de rendu."""

from collections import OrderedDict


class FrameCache:
    def __init__(self, max_bytes=64 * 1024 * 1024):
        self.max_bytes = max_bytes
        self.size = 0
        self.frames = OrderedDict()

    def get(self, key):
        image = self.frames.get(key)
        if image is not None:
            self.frames.move_to_end(key)
        return image

    def put(self, key, image):
        if key in self.frames:
            self.size -= self.frames.pop(key).nbytes
        if image.nbytes > self.max_bytes:
            return
        image.setflags(write=False)
        self.frames[key] = image
        self.size += image.nbytes
        while self.size > self.max_bytes:
            self.size -= self.frames.popitem(last=False)[1].nbytes

    def clear(self):
        self.frames.clear()
        self.size = 0
