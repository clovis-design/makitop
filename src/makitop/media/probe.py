"""Analyse d'un fichier source : type, durée, résolution, FPS, codecs (PyAV et Pillow)."""

from pathlib import Path

import av
from PIL import Image, UnidentifiedImageError

from makitop.model.media import Media, MediaKind

VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"})
AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"})
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS


class MediaProbeError(Exception):
    """Le fichier n'existe pas, n'est pas supporté ou ne peut pas être lu."""


def probe(path: Path) -> Media:
    path = Path(path)
    if not path.is_file():
        raise MediaProbeError(f"Fichier introuvable : {path.name}")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise MediaProbeError(f"Format non supporté : {suffix or '(sans extension)'}")
    if suffix in IMAGE_EXTENSIONS:
        return _probe_image(path)
    return _probe_av(path)


def _probe_image(path: Path) -> Media:
    try:
        with Image.open(path) as image:
            image.verify()
            width, height = image.size
    except (UnidentifiedImageError, OSError) as error:
        raise MediaProbeError(f"Image illisible : {path.name}") from error
    return Media(path=path, kind=MediaKind.IMAGE, width=width, height=height)


def _probe_av(path: Path) -> Media:
    try:
        with av.open(str(path)) as container:
            video = _first_video_stream(container)
            audio = next(iter(container.streams.audio), None)
            if video is None and audio is None:
                raise MediaProbeError(f"Aucune piste vidéo ni audio : {path.name}")

            info: dict = {"duration": _duration(container, video or audio)}
            if video is not None:
                info |= {
                    "width": video.codec_context.width,
                    "height": video.codec_context.height,
                    "fps": float(video.average_rate) if video.average_rate else None,
                    "video_codec": video.codec_context.name,
                }
            if audio is not None:
                info |= {
                    "audio_codec": audio.codec_context.name,
                    "sample_rate": audio.codec_context.sample_rate,
                    "channels": audio.codec_context.channels,
                }
    except av.FFmpegError as error:
        raise MediaProbeError(f"Fichier illisible : {path.name}") from error

    kind = MediaKind.VIDEO if video is not None else MediaKind.AUDIO
    return Media(path=path, kind=kind, **info)


def _first_video_stream(container):
    # Les pochettes d'album (MP3, M4A) sont des pistes vidéo « attached_pic » : on les ignore.
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
