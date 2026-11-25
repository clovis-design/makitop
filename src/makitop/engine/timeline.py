"""Composition des vidéos et images actives, du fond vers le premier plan."""

import math
from collections import OrderedDict

import cv2
import numpy as np
from PIL import Image, ImageOps

from makitop.engine import text, transitions
from makitop.engine.cache import FrameCache
from makitop.engine.decoder import MediaDecoder
from makitop.engine.effects import video as video_effects
from makitop.model.composition import FORMATS, fitted_bounds
from makitop.model.effects import TIME_DEPENDENT
from makitop.model.media import MediaKind
from makitop.model.timeline import ImageClip, MediaClip, TextClip


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
        clips = [c for c in project.timeline.clips_at(time)
                 if isinstance(c, TextClip) or c.media.kind != MediaKind.AUDIO]
        active, hidden = [], set()
        for span in project.timeline.transition_spans():
            if span.start <= time < span.end:
                pair = {span.incoming.id, span.outgoing.id}
                if hidden.isdisjoint(pair):
                    hidden.update(pair)
                    active.append(span)
            elif span.end <= time < span.suppress_until:
                hidden.add(span.outgoing.id)
        if hidden:
            clips = [c for c in clips if c.id not in hidden]
        if active:
            return self._render_transitions(clips, active, time, frame_index, width, height)
        sources = []
        local_times = [time - c.timeline_start for c in clips]
        transforms = [c.transform_at(t) for c, t in zip(clips, local_times, strict=True)]
        for clip, local_time, transform in zip(clips, local_times, transforms, strict=True):
            if isinstance(clip, TextClip):
                sources.append((("text", clip.content, clip.style, clip.opacity_at(local_time),
                                 clip.font_scale_at(local_time, transform)), None))
                continue
            identity = self._identity(clip)
            source_time = clip.source_time_at(time) if isinstance(clip, MediaClip) else None
            sources.append((identity, None if source_time is None else round(source_time, 9)))
        # Une image fixe avec un effet animé change à chaque frame : le temps local
        # du clip fait alors partie de la clé.
        key = ("composition", width, height, tuple(
            (s, transform, c.track, c.effects,
             (round(t, 6), c.duration)
             if any(e.kind in TIME_DEPENDENT for e in c.effects) else None)
            for s, c, t, transform in zip(sources, clips, local_times, transforms, strict=True)))
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        result = np.zeros((height, width, 3), dtype=np.uint8)
        for clip, (identity, source_time), local_t, transform in zip(
            clips, sources, local_times, transforms, strict=True,
        ):
            if isinstance(clip, TextClip):
                opacity, font_scale = identity[-2:]
                text.composite(result, clip.content, clip.style, transform,
                               opacity=opacity, font_scale=font_scale)
                continue
            image = self._source(clip, identity, source_time)
            self._composite(result, image, transform, clip.effects,
                            local_t, clip.duration, frame_index)
        self.cache.put(key, result)
        return result

    @staticmethod
    def _identity(clip):
        stat = clip.media.path.stat()
        return str(clip.media.path.resolve()), stat.st_mtime_ns, stat.st_size

    def _draw_at(self, canvas, clip, time, frame_index):
        local = min(clip.duration, max(0, time - clip.timeline_start))
        transform = clip.transform_at(local)
        if isinstance(clip, TextClip):
            text.composite(canvas, clip.content, clip.style, transform,
                           opacity=clip.opacity_at(local),
                           font_scale=clip.font_scale_at(local, transform))
            return
        source = None
        if isinstance(clip, MediaClip):
            # Utiliser les poignées du rush si disponibles. Sinon garder l'image de bord.
            source = max(0, clip.source_start + (time - clip.timeline_start) * clip.speed)
            if clip.media.duration is not None:
                source = min(source, max(0, clip.media.duration - 1e-6))
        image = self._source(clip, self._identity(clip), source)
        self._composite(canvas, image, transform, clip.effects, local, clip.duration, frame_index)

    def _render_transitions(self, clips, spans, time, frame_index, width, height):
        result = np.zeros((height, width, 3), dtype=np.uint8)
        layers = [(clip.track, clip, None) for clip in clips]
        layers.extend((max(span.incoming.track, span.outgoing.track), None, span)
                      for span in spans)
        for _, clip, span in sorted(layers, key=lambda entry: entry[0]):
            if span is None:
                self._draw_at(result, clip, time, frame_index)
                continue
            a = np.zeros((height, width, 4), dtype=np.uint8)
            b = np.zeros_like(a)
            self._draw_at(a, span.outgoing, time, frame_index)
            self._draw_at(b, span.incoming, time, frame_index)
            rgba = transitions.blend(a, b, span.transition.kind, span.progress(time))
            alpha = rgba[..., 3:4].astype(np.float32) / 255
            result[:] = np.clip(np.rint(rgba[..., :3] + result * (1 - alpha)), 0, 255)
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
        matrix = None
        if t.rotation:
            center = ((w - 1) / 2, (h - 1) / 2)
            matrix = cv2.getRotationMatrix2D(center, -t.rotation, 1)
            cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
            # Restreindre la déformation à la zone visible du cadre.
            cx, cy = x + center[0], y + center[1]
            rx, ry = (cos * w + sin * h) / 2, (sin * w + cos * h) / 2
            x0, y0 = max(0, math.floor(cx - rx)), max(0, math.floor(cy - ry))
            x1, y1 = min(width, math.ceil(cx + rx + 1)), min(height, math.ceil(cy + ry + 1))
        else:
            x0, y0, x1, y1 = max(0, x), max(0, y), min(width, x + w), min(height, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        interpolation = (cv2.INTER_AREA if w <= image.shape[1] and h <= image.shape[0]
                         else cv2.INTER_LANCZOS4)
        resized = cv2.resize(image, (w, h), interpolation=interpolation)
        # Effets appliqués à la taille d'affichage : leur coût ne dépend pas de la source.
        scaled = video_effects.apply(resized, effects, local_t, duration, frame_index)
        if t.flip_horizontal or t.flip_vertical:
            axis = -1 if t.flip_horizontal and t.flip_vertical else int(t.flip_horizontal)
            scaled = cv2.flip(scaled, axis)
        target = canvas[y0:y1, x0:x1]
        if matrix is not None:
            matrix[:, 2] += (x - x0, y - y0)
            TimelineRenderer._composite_rotated(target, scaled, matrix)
            return
        scaled = scaled[y0 - y:y1 - y, x0 - x:x1 - x]
        if target.shape[2] == 4:
            if scaled.shape[2] == 4:
                target[..., 3] = scaled[..., 3]
                alpha = scaled[..., 3:4].astype(np.float32) / 255
                target[..., :3] = np.rint(scaled[..., :3] * alpha)
            else:
                target[..., :3] = scaled
                target[..., 3] = 255
            return
        if scaled.shape[2] == 4:
            alpha = scaled[:, :, 3:4].astype(np.float32) / 255
            target[:] = np.rint(scaled[:, :, :3] * alpha + target * (1 - alpha)).astype(np.uint8)
        else:
            target[:] = scaled

    @staticmethod
    def _composite_rotated(target, image, matrix):
        # Une bordure transparente (et non noire) laisse voir les calques derrière.
        rgba = np.empty((*image.shape[:2], 4), dtype=np.float32)
        rgba[..., :3] = image[..., :3]
        rgba[..., 3] = image[..., 3] / 255 if image.shape[2] == 4 else 1
        rgba[..., :3] *= rgba[..., 3:4]
        height, width = target.shape[:2]
        rotated = cv2.warpAffine(rgba, matrix, (width, height), flags=cv2.INTER_LINEAR)
        if target.shape[2] == 4:
            target[..., :3] = np.rint(rotated[..., :3])
            target[..., 3] = np.rint(rotated[..., 3] * 255)
        else:
            target[:] = np.rint(rotated[..., :3] + target * (1 - rotated[..., 3:4]))

    def close(self):
        for decoder in self.decoders.values():
            decoder.close()
        self.decoders.clear()
        self.cache.clear()
