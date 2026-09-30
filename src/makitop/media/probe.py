"""Analyse d'un fichier source : type, durée, résolution, FPS, codecs (PyAV et Pillow)."""

from pathlib import Path

import av
from PIL import Image as PilImage
from PIL import UnidentifiedImageError

from makitop.model.media import Audio, Image, Video

VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"})
AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"})
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS


class MediaProbeError(Exception):
    """Le fichier n'existe pas, n'est pas supporté ou ne peut pas être lu."""


def probe(path: Path) -> Video | Audio | Image:
    path = Path(path)
    if not path.is_file():
        raise MediaProbeError(f"Fichier introuvable : {path.name}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise MediaProbeError(f"Format non supporté : {suffix or '(sans extension)'}")
    if suffix in IMAGE_EXTENSIONS:
        return _probe_image(path)
    return _probe_av(path)


def _probe_image(path: Path) -> Image:
    try:
        with PilImage.open(path) as image:
            image.verify()
            width, height = image.size
    except (UnidentifiedImageError, OSError) as error:
        raise MediaProbeError(f"Image illisible : {path.name}") from error
    return Image(path=path, width=width, height=height)


def _probe_av(path: Path) -> Video | Audio:
    try:
        with av.open(str(path)) as container:
            video_stream = _first_video_stream(container)
            audio_stream = next(iter(container.streams.audio), None)
            if video_stream is None and audio_stream is None:
                raise MediaProbeError(f"Aucune piste vidéo ni audio : {path.name}")

            duration = _duration(container, video_stream or audio_stream)

            if video_stream is not None:
                audio_info = {}
                if audio_stream is not None:
                    audio_info = {
                        "audio_codec": audio_stream.codec_context.name,
                        "sample_rate": audio_stream.codec_context.sample_rate,
                        "channels": audio_stream.codec_context.channels,
                    }
                return Video(
                    path=path,
                    duration=duration,
                    width=video_stream.codec_context.width,
                    height=video_stream.codec_context.height,
                    fps=float(video_stream.average_rate) if video_stream.average_rate else None,
                    video_codec=video_stream.codec_context.name,
                    **audio_info,
                )

            return Audio(
                path=path,
                duration=duration,
                audio_codec=audio_stream.codec_context.name,
                sample_rate=audio_stream.codec_context.sample_rate,
                channels=audio_stream.codec_context.channels,
            )
    except av.FFmpegError as error:
        raise MediaProbeError(f"Fichier illisible : {path.name}") from error


def _first_video_stream(container):
    for stream in container.streams.video:
        if not stream.disposition & av.stream.Disposition.attached_pic:
            return stream
    return None


def _duration(container, stream) -> float | None:
    if stream.duration is not None and stream.time_base is not None:
        return float(stream.duration * stream.time_base)
    if container.duration is not None:
        return container.duration / av.time_base
    return None
