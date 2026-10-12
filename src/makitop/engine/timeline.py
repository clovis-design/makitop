"""Rendu de la piste vidéo à un temps du montage, indépendant de l'interface."""

from collections import OrderedDict

import cv2
import numpy as np

from makitop.engine.cache import FrameCache
from makitop.engine.decoder import MediaDecoder


class TimelineRenderer:
    def __init__(self, width=640, height=360, cache_bytes=64 * 1024 * 1024):
        self.width, self.height = width, height
        self.cache = FrameCache(cache_bytes)
        self.decoders = OrderedDict()

    def render(self, project, frame_index):
        time = frame_index / project.timeline.fps
        clip = project.timeline.clip_at(time)
        if clip is None:
            return np.zeros((self.height, self.width, 3), dtype=np.uint8)
        media = next(m for m in project.media if m.id == clip.media_id)
        stat = media.path.stat()
        identity = (str(media.path.resolve()), stat.st_mtime_ns, stat.st_size)
        source_time = max(clip.source_in, clip.source_in + time - clip.timeline_start)
        key = (identity, round(source_time, 9), self.width, self.height)
        image = self.cache.get(key)
        if image is not None:
            return image
        if identity not in self.decoders:
            decoder = MediaDecoder()
            try:
                decoder.open(media.path)
            except Exception:
                decoder.close()
                raise
            self.decoders[identity] = decoder
        self.decoders.move_to_end(identity)
        while len(self.decoders) > 3:
            self.decoders.popitem(last=False)[1].close()
        image = self.decoders[identity].sample_at(source_time)
        if image is None:
            raise ValueError(f"Aucune image lisible : {media.name}")
        # Letterboxing : conserver le rapport d'aspect de la source.
        h, w = image.shape[:2]
        ratio = min(self.width / w, self.height / h)
        w, h = max(1, round(w * ratio)), max(1, round(h * ratio))
        result = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        x, y = (self.width - w) // 2, (self.height - h) // 2
        result[y:y + h, x:x + w] = cv2.resize(image, (w, h))
        self.cache.put(key, result)
        return result

    def close(self):
        for decoder in self.decoders.values():
            decoder.close()
        self.decoders.clear()
        self.cache.clear()
