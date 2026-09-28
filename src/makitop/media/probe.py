from pathlib import Path

import av

from makitop.model.media import Video


class ProbeError(Exception):
    pass


def probe(path: Path) -> Video:
    path = Path(path)

    if not path.exists():
        raise ProbeError(f"Fichier introuvable : {path}")

    try:
        container = av.open(str(path))
    except av.InvalidDataError as exc:
        raise ProbeError(f"Format non supporté : {path}") from exc

    try:
        video_streams = [s for s in container.streams if s.type == "video"]
        if not video_streams:
            raise ProbeError(f"Aucun stream vidéo dans : {path}")

        stream = video_streams[0]

        duration = float(container.duration * av.time_base) if container.duration else 0.0
        fps = float(stream.average_rate) if stream.average_rate else 0.0

        return Video(
            path=path,
            duration=duration,
            width=stream.width,
            height=stream.height,
            fps=fps,
        )
    finally:
        container.close()
