"""Décodage audio séquentiel et rendu des portions du montage, en stéréo 48 kHz."""

import av
import numpy as np

from makitop.model.timeline import MediaClip

SAMPLE_RATE = 48000


class AudioDecoder:
    def __init__(self, path):
        self.container = av.open(str(path))
        self.stream = next(iter(self.container.streams.audio), None)
        self.frames = iter(())
        self.ahead = None
        self.position = None

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
        if self.position is None or start < self.position or start - self.position > SAMPLE_RATE:
            # Un peu de pré-roll permet au rééchantillonneur de retrouver son état.
            timestamp = int(max(0, start / SAMPLE_RATE - 0.1) / self.stream.time_base)
            self.container.seek(timestamp, stream=self.stream, backward=True)
            self.frames = self._frames()
            self.ahead = None
        end = start + count
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
            left, right = max(start, offset), min(end, offset + len(samples))
            if right > left:
                result[left - start:right - start] = samples[left - offset:right - offset]
            if offset + len(samples) > end:
                break
            self.ahead = None
        self.position = end
        return result

    def close(self):
        self.container.close()


class TimelineAudioRenderer:
    def __init__(self):
        self.decoder = None
        self.path = None

    def render(self, project, start, count):
        result = np.zeros((count, 2), dtype=np.float32)
        # Même priorité que Timeline.clip_at en cas de chevauchement.
        occupied = np.zeros(count, dtype=bool)
        for clip in project.timeline.clips:
            clip_start = round(clip.timeline_start * SAMPLE_RATE)
            left = max(start, clip_start)
            right = min(start + count, round(clip.timeline_end * SAMPLE_RATE))
            if right <= left:
                continue
            region = slice(left - start, right - start)
            if isinstance(clip, MediaClip) and clip.media.has_audio:
                if self.path != clip.media.path:
                    self.close()
                    self.decoder = AudioDecoder(clip.media.path)
                    self.path = clip.media.path
                source = round(clip.source_start * SAMPLE_RATE) + left - clip_start
                samples = self.decoder.read(source, right - left)
                np.copyto(result[region], samples, where=~occupied[region, None])
            occupied[region] = True
        return result

    def close(self):
        if self.decoder is not None:
            self.decoder.close()
        self.decoder = None
        self.path = None
