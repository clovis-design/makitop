"""Export du montage en H.264/AAC avec les mêmes moteurs que la prévisualisation."""

import math
import os
import tempfile
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from makitop.engine.audio import SAMPLE_RATE, TimelineAudioRenderer
from makitop.engine.timeline import TimelineRenderer
from makitop.model.composition import FORMATS


class ExportCancelled(Exception):
    """Annulation demandée par l'utilisateur."""


@dataclass(frozen=True)
class ExportSettings:
    """Résolution du petit côté, cadence et qualité de l'export."""

    height: int = 1080
    fps: int | None = None
    crf: int = 18
    preset: str = "medium"

    def __post_init__(self):
        if self.height not in (360, 720, 1080, 2160):
            raise ValueError("Résolution d'export inconnue.")
        if self.fps is not None and (type(self.fps) is not int or not 1 <= self.fps <= 120):
            raise ValueError("La cadence doit être comprise entre 1 et 120 fps.")
        if type(self.crf) is not int or not 0 <= self.crf <= 51:
            raise ValueError("Qualité H.264 invalide.")
        if self.preset not in ("fast", "medium", "slow"):
            raise ValueError("Préréglage H.264 inconnu.")


def export_mp4(project, path, *, settings=None, progress=None, cancel=None):
    """Écrit un MP4 puis remplace la destination uniquement après réussite.

    L'appelant fournit un instantané du projet s'il peut être modifié en parallèle.
    Les callbacks ne doivent pas manipuler l'interface depuis le thread d'export.
    """
    settings = settings or ExportSettings()
    if settings.fps is not None:
        project = replace(project, timeline=replace(project.timeline, fps=settings.fps))
    path = Path(path).absolute()
    if path.suffix.lower() != ".mp4":
        path = path.with_name(path.name + ".mp4")
    if project.timeline.duration <= 0:
        raise ValueError("La timeline est vide. Ajoutez un média avant d'exporter.")
    sources = [m.path for m in project.media] + [c.media.path for c in project.timeline.clips]
    if any(path.resolve() == source.resolve() for source in sources):
        raise ValueError("Le fichier exporté ne peut pas remplacer un média source.")
    width, height = FORMATS[project.canvas_format]
    width, height = width * settings.height // 1080, height * settings.height // 1080
    fps = project.timeline.fps
    frame_count = max(1, math.ceil(project.timeline.duration * fps - 1e-9))
    sample_count = math.ceil(frame_count * SAMPLE_RATE / fps)
    video_renderer = TimelineRenderer(width, height)
    audio_renderer = TimelineAudioRenderer()
    temporary = None

    def check_cancelled():
        if cancel is not None and cancel.is_set():
            raise ExportCancelled()

    try:
        check_cancelled()
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".mp4", delete=False) as file:
            temporary = Path(file.name)
        with av.open(str(temporary), "w", format="mp4", options={"movflags": "+faststart"}) as out:
            video = out.add_stream("libx264", rate=fps)
            video.width, video.height = width, height
            video.pix_fmt = "yuv420p"
            video.options = {"crf": str(settings.crf), "preset": settings.preset}
            audio = out.add_stream("aac", rate=SAMPLE_RATE)
            audio.layout = "stereo"
            audio.bit_rate = 256000
            sample = 0
            for index in range(frame_count):
                check_cancelled()
                image = video_renderer.render(project, index)
                frame = av.VideoFrame.from_ndarray(image, format="rgb24")
                frame.pts, frame.time_base = index, Fraction(1, fps)
                for packet in video.encode(frame):
                    out.mux(packet)
                target = min(sample_count, math.ceil((index + 1) * SAMPLE_RATE / fps))
                while sample < target:
                    check_cancelled()
                    count = min(1024, target - sample)
                    samples = audio_renderer.render(project, sample, count)
                    frame = av.AudioFrame.from_ndarray(
                        np.ascontiguousarray(samples.T), format="fltp", layout="stereo",
                    )
                    frame.sample_rate = SAMPLE_RATE
                    frame.pts, frame.time_base = sample, Fraction(1, SAMPLE_RATE)
                    for packet in audio.encode(frame):
                        out.mux(packet)
                    sample += count
                if progress:
                    progress((index + 1) / frame_count)
            for stream in (video, audio):
                for packet in stream.encode(None):
                    out.mux(packet)
        check_cancelled()
        os.replace(temporary, path)
        return path
    finally:
        video_renderer.close()
        audio_renderer.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)
