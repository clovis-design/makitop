"""Sortie audio : préchargement hors UI et callback sans décodage ni accès disque."""

from threading import Event, Thread

from makitop.engine.audio import SAMPLE_RATE, TimelineAudioRenderer
from makitop.model.timeline import MediaClip

BLOCK_SIZE = 2048
PREFETCH_BLOCKS = 12


class AudioPlayer:
    def __init__(self, renderer_factory=TimelineAudioRenderer, stream_factory=None):
        self.renderer_factory = renderer_factory
        self.stream_factory = stream_factory
        self.thread = None
        self.cancelled = Event()
        self.error = None

    def start(self, project, clock):
        self.stop()
        if not any(isinstance(c, MediaClip) and c.media.has_audio for c in project.timeline.clips):
            return
        self.cancelled = Event()
        self.thread = Thread(
            target=self._run, args=(project, clock, self.cancelled),
            name="makitop-audio", daemon=True,
        )
        self.thread.start()

    def _run(self, project, clock, cancelled):
        renderer = self.renderer_factory()
        stream = None
        blocks = {}
        end = round(project.timeline.duration * SAMPLE_RATE)

        def callback(outdata, frames, timing, status):
            outdata.fill(0)
            if cancelled.is_set() or not clock.playing:
                return
            # Le son sera entendu à outputBufferDacTime : compenser la latence
            # du périphérique pour rester sur l'horloge utilisée par la vidéo.
            delay = max(0.0, timing.outputBufferDacTime - timing.currentTime)
            start = max(0, round((clock.current_time() + delay) * SAMPLE_RATE))
            snapshot = blocks
            cursor = start
            while cursor < min(start + frames, end):
                index, offset = divmod(cursor, BLOCK_SIZE)
                count = min(BLOCK_SIZE - offset, start + frames - cursor, end - cursor)
                block = snapshot.get(index)
                if block is not None:
                    outdata[cursor - start:cursor - start + count] = block[offset:offset + count]
                cursor += count

        try:
            factory = self.stream_factory
            if factory is None:
                import sounddevice as sd

                factory = sd.OutputStream
            while not cancelled.is_set() and clock.playing:
                first = max(0, int(clock.current_time() * SAMPLE_RATE) // BLOCK_SIZE)
                if first * BLOCK_SIZE >= end:
                    break
                wanted = range(first, first + PREFETCH_BLOCKS)
                updated = {i: blocks[i] for i in wanted if i in blocks}
                for index in wanted:
                    if cancelled.is_set():
                        return
                    if index not in updated:
                        updated[index] = renderer.render(project, index * BLOCK_SIZE, BLOCK_SIZE)
                # Publication atomique ; le callback conserve son propre instantané.
                blocks = updated
                if stream is None:
                    stream = factory(
                        samplerate=SAMPLE_RATE, channels=2, dtype="float32",
                        blocksize=BLOCK_SIZE, latency="low", callback=callback,
                    )
                    if cancelled.is_set():
                        return
                    stream.start()
                cancelled.wait(0.01)
        except Exception as exc:
            if not cancelled.is_set():
                self.error = exc
        finally:
            try:
                if stream is not None:
                    try:
                        stream.abort()
                    finally:
                        stream.close()
            finally:
                renderer.close()

    def check_error(self):
        error, self.error = self.error, None
        if error is not None:
            raise RuntimeError(f"Lecture audio impossible : {error}") from error

    def stop(self):
        self.cancelled.set()
        if self.thread is not None:
            self.thread.join()
            self.thread = None
        self.error = None

    def close(self):
        self.stop()
