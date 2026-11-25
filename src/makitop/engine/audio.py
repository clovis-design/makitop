"""Décodage audio séquentiel et rendu des portions du montage, en stéréo 48 kHz."""

from itertools import pairwise

import av
import numpy as np

from makitop.model.keyframes import curve, interpolate
from makitop.model.timeline import MAX_CLIP_SPEED, MediaClip

SAMPLE_RATE = 48000
_FILTER_LOBES = 4
_READ_OVERLAP = int(2 * _FILTER_LOBES * MAX_CLIP_SPEED) + 2


class AudioDecoder:
    def __init__(self, path):
        self.container = av.open(str(path))
        self.stream = next(iter(self.container.streams.audio), None)
        self.frames = iter(())
        self.ahead = None
        self.position = None
        self._tail = np.empty((0, 2), dtype=np.float32)

    def _frames(self):
        resampler = av.AudioResampler(format="fltp", layout="stereo", rate=SAMPLE_RATE)
        for frame in self.container.decode(self.stream):
            yield from resampler.resample(frame)
        yield from resampler.resample(None)

    def read(self, start, count):
        """Renvoie exactement count échantillons, avec silence hors de la piste audio."""
        result = np.zeros((count, 2), dtype=np.float32)
        if self.stream is None:
            return result
        first = start
        end = start + count
        if self.position is not None and self.position - len(self._tail) <= start < self.position:
            # Les blocs rééchantillonnés partagent quelques échantillons aux frontières.
            left = start - (self.position - len(self._tail))
            first = min(end, self.position)
            result[:first - start] = self._tail[left:left + first - start]
            if first == end:
                return result
        if (self.position is None or first < self.position
                or first - self.position > SAMPLE_RATE):
            # Un peu de pré-roll permet au rééchantillonneur de retrouver son état.
            timestamp = int(max(0, first / SAMPLE_RATE - 0.1) / self.stream.time_base)
            self.container.seek(timestamp, stream=self.stream, backward=True)
            self.frames = self._frames()
            self.ahead = None
        while True:
            if self.ahead is None:
                frame = next(self.frames, None)
                if frame is None:
                    break
                if frame.time is None:
                    continue
                self.ahead = (round(frame.time * SAMPLE_RATE), frame.to_ndarray().T.copy())
            offset, samples = self.ahead
            if offset >= end:
                break
            left, right = max(first, offset), min(end, offset + len(samples))
            if right > left:
                result[left - start:right - start] = samples[left - offset:right - offset]
            if offset + len(samples) > end:
                break
            self.ahead = None
        self.position = end
        self._tail = result[-_READ_OVERLAP:].copy()
        return result

    def close(self):
        self.container.close()


class TimelineAudioRenderer:
    def __init__(self):
        self.decoders = {}

    @property
    def decoder(self):
        return next(iter(self.decoders.values()), None)

    def render(self, project, start, count):
        result = np.zeros((count, 2), dtype=np.float32)
        active = set()
        spans = project.timeline.transition_spans()
        entering = {span.incoming.id: span for span in spans}
        leaving = {span.outgoing.id: span for span in spans}
        for clip in project.timeline.clips:
            clip_start = round(clip.timeline_start * SAMPLE_RATE)
            in_span, out_span = entering.get(clip.id), leaving.get(clip.id)
            first, last = clip_start, round(clip.timeline_end * SAMPLE_RATE)
            if isinstance(clip, MediaClip) and (in_span or out_span):
                if in_span:
                    first = min(first, round(in_span.start * SAMPLE_RATE))
                if out_span:
                    last = max(last, round(out_span.end * SAMPLE_RATE))
                source_start = round(clip.source_start * SAMPLE_RATE)
                first = max(first, clip_start + int(np.ceil(-source_start / clip.speed)))
                if clip.media.duration is not None:
                    source_remaining = clip.media.duration - clip.source_start
                    remaining_samples = round(source_remaining * SAMPLE_RATE / clip.speed)
                    last = min(last, clip_start + remaining_samples)
            left, right = max(start, first), min(start + count, last)
            if right <= left:
                continue
            region = slice(left - start, right - start)
            if (isinstance(clip, MediaClip) and clip.media.has_audio
                    and not clip.muted
                    and (clip.volume > 0 or any(k.property == "volume" for k in clip.keyframes))):
                # Deux occurrences de la même source peuvent jouer à des temps différents.
                active.add(clip.id)
                if clip.id not in self.decoders:
                    self.decoders[clip.id] = AudioDecoder(clip.media.path)
                samples = _read_clip_audio(self.decoders[clip.id], clip,
                                           left - clip_start, right - left,
                                           handles=bool(in_span or out_span))
                points = curve(clip.keyframes, "volume")
                if points or in_span or out_span:
                    # Enveloppe par échantillon, indépendante des blocs de lecture/export.
                    times = (np.arange(left, right) - clip_start) / SAMPLE_RATE
                    gain = (np.interp(times, [k.time for k in points], [k.value for k in points])
                            if points else np.full(right - left, clip.volume))
                    for a, b in pairwise(points):
                        if a.interpolation != "linear":
                            mask = (times >= a.time) & (times < b.time)
                            gain[mask] = interpolate(a, b, times[mask])
                    absolute = np.arange(left, right) / SAMPLE_RATE
                    if in_span:
                        gain *= np.clip(in_span.progress(absolute), 0, 1)
                    if out_span:
                        within = absolute < out_span.suppress_until
                        gain[within] *= 1 - np.clip(out_span.progress(absolute[within]), 0, 1)
                    result[region] += samples * gain[:, None]
                else:
                    result[region] += samples * clip.volume
        for clip_id in set(self.decoders) - active:
            self.decoders.pop(clip_id).close()
        return np.clip(result, -1, 1, out=result)

    def close(self):
        for decoder in self.decoders.values():
            decoder.close()
        self.decoders.clear()


def _read_clip_audio(decoder, clip, offset, count, *, handles=False):
    source = round(clip.source_start * SAMPLE_RATE)
    if clip.speed == 1:
        return decoder.read(source + offset, count)
    minimum = 0 if handles else source
    positions = source + (offset + np.arange(count)) * clip.speed
    if handles:
        last = (int(positions[-1]) + _READ_OVERLAP if clip.media.duration is None else
                max(0, round(clip.media.duration * SAMPLE_RATE) - 1))
    else:
        last = max(source, round(clip.source_end * SAMPLE_RATE) - 1)
    positions = np.clip(positions, minimum, last)
    indices = positions.astype(np.int64)
    if clip.speed < 1:
        first, end = indices[0], min(last, indices[-1] + 1)
        data = decoder.read(first, end - first + 1)
        alpha = (positions - indices).astype(np.float32)[:, None]
        following = np.minimum(indices + 1, last)
        return data[indices - first] * (1 - alpha) + data[following - first] * alpha

    # À l'accélération, filtrer avant de décimer pour éviter le repliement spectral.
    radius = int(np.ceil(_FILTER_LOBES * clip.speed))
    taps = indices[:, None] + np.arange(1 - radius, radius + 1)
    distance = positions[:, None] - taps
    weights = np.sinc(distance / clip.speed) * np.sinc(distance / radius)
    weights /= weights.sum(axis=1, keepdims=True)
    taps = np.clip(taps, minimum, last)
    first, end = taps[0, 0], taps[-1, -1]
    data = decoder.read(first, end - first + 1)
    return np.einsum("ij,ijk->ik", weights.astype(np.float32), data[taps - first])
