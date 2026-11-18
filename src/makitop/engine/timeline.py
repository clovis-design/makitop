"""Composition des vidéos et images actives, du fond vers le premier plan."""

from collections import OrderedDict

import cv2
import numpy as np
from PIL import Image, ImageOps

from makitop.engine.cache import FrameCache
from makitop.engine.decoder import MediaDecoder
from makitop.engine.effects import video as video_effects
from makitop.model.composition import FORMATS, fitted_bounds
from makitop.model.effects import TIME_DEPENDENT
from makitop.model.media import MediaKind
from makitop.model.timeline import ImageClip


class TimelineRenderer:
    def __init__(self, width=None, height=None, cache_bytes=128 * 1024 * 1024):
        # Une taille explicite sert notamment aux miniatures et aux tests du moteur.
        self.explicit_size = width is not None and height is not None
        self.width, self.height = width or 640, height or 360
        self.preview_height = 720
        self.cache = FrameCache(cache_bytes)
        self.decoders = OrderedDict()

    def set_preview_height(self, height):
        if height not in (360, 720, 1080):
            raise ValueError("Qualité de prévisualisation inconnue.")
        self.preview_height = height

    def render(self, project, frame_index):
        time = frame_index / project.timeline.fps
        width, height = self.width, self.height
        if not self.explicit_size:
            w, h = FORMATS[project.canvas_format]
            width, height = round(w * self.preview_height / 1080), round(
                h * self.preview_height / 1080,
            )
        clips = [c for c in project.timeline.clips_at(time) if c.media.kind != MediaKind.AUDIO]
        sources = []
        local_times = [time - c.timeline_start for c in clips]
        transforms = [c.transform_at(t) for c, t in zip(clips, local_times, strict=True)]
        for clip in clips:
            stat = clip.media.path.stat()
            identity = (str(clip.media.path.resolve()), stat.st_mtime_ns, stat.st_size)
            source_time = (None if isinstance(clip, ImageClip) else
                           max(clip.source_start, clip.source_start + time - clip.timeline_start))
            sources.append((identity, None if source_time is None else round(source_time, 9)))
        # Une image fixe avec un effet animé change à chaque frame : le temps local
        # du clip fait alors partie de la clé.
        key = ("composition", width, height, tuple(
            (s, transform, c.track, c.effects,
             round(t, 6) if any(e.kind in TIME_DEPENDENT for e in c.effects) else None)
            for s, c, t, transform in zip(sources, clips, local_times, transforms, strict=True)))
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        result = np.zeros((height, width, 3), dtype=np.uint8)
        for clip, (identity, source_time), local_t, transform in zip(
            clips, sources, local_times, transforms, strict=True,
        ):
            image = self._source(clip, identity, source_time)
            self._composite(result, image, transform, clip.effects,
                            local_t, clip.duration, frame_index)
        self.cache.put(key, result)
        return result

    def _source(self, clip, identity, source_time):
        key = ("source", identity, source_time)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        if isinstance(clip, ImageClip):
            with Image.open(clip.media.path) as source:
                image = np.asarray(ImageOps.exif_transpose(source).convert("RGBA"))
        else:
            # Deux calques issus d'un même fichier gardent chacun leur curseur :
            # sinon chaque image peut provoquer deux seeks vers des temps éloignés.
            decoder_key = (clip.id, identity)
            if decoder_key not in self.decoders:
                decoder = MediaDecoder()
                try:
                    decoder.open(clip.media.path)
                except Exception:
                    decoder.close()
                    raise
                self.decoders[decoder_key] = decoder
            self.decoders.move_to_end(decoder_key)
            while len(self.decoders) > 8:
                self.decoders.popitem(last=False)[1].close()
            image = self.decoders[decoder_key].sample_at(source_time)
        if image is None:
            raise ValueError(f"Aucune image lisible : {clip.media.name}")
        self.cache.put(key, image)
        return image

    @staticmethod
    def _composite(canvas, image, transform, effects=(), local_t=0.0, duration=1.0, frame_index=0):
        height, width = canvas.shape[:2]
        h, w = image.shape[:2]
        x, y, box_w, box_h = fitted_bounds(transform, w, h, width / height)
        t = transform
        left, top = int(t.crop_left * w), int(t.crop_top * h)
        right, bottom = max(left + 1, round((1 - t.crop_right) * w)), max(
            top + 1, round((1 - t.crop_bottom) * h),
        )
        image = image[top:bottom, left:right]
        x, y = round(x * width), round(y * height)
        w, h = max(1, round(box_w * width)), max(1, round(box_h * height))
        x0, y0, x1, y1 = max(0, x), max(0, y), min(width, x + w), min(height, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        interpolation = (cv2.INTER_AREA if w <= image.shape[1] and h <= image.shape[0]
                         else cv2.INTER_LANCZOS4)
        resized = cv2.resize(image, (w, h), interpolation=interpolation)
        # Effets appliqués à la taille d'affichage : leur coût ne dépend pas de la source.
        scaled = video_effects.apply(resized, effects, local_t, duration,
                                     frame_index)[y0 - y:y1 - y, x0 - x:x1 - x]
        target = canvas[y0:y1, x0:x1]
        if scaled.shape[2] == 4:
            alpha = scaled[:, :, 3:4].astype(np.float32) / 255
            target[:] = np.rint(scaled[:, :, :3] * alpha + target * (1 - alpha)).astype(np.uint8)
        else:
            target[:] = scaled

    def close(self):
        for decoder in self.decoders.values():
            decoder.close()
        self.decoders.clear()
        self.cache.clear()
