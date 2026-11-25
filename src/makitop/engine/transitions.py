"""Transitions sans état : PyAV peut rendre n'importe quel instant, dans le désordre."""

from fractions import Fraction
from functools import cache

import av
import cv2

_TIME_BASE = Fraction(1, 1_000_000)


@cache
def is_available(kind):
    if "xfade" not in av.filter.filters_available:
        return kind == "fade"
    try:
        av.filter.Graph().add("xfade", f"transition={kind}")
    except av.FFmpegError:
        return kind == "fade"
    return True


def blend(outgoing, incoming, kind, progress):
    """Mélange deux calques RGBA prémultipliés de même taille."""
    if progress <= 0:
        return outgoing
    if progress >= 1:
        return incoming
    if kind == "fade" or not is_available(kind):
        return cv2.addWeighted(outgoing, 1 - progress, incoming, progress, 0)

    height, width = outgoing.shape[:2]
    args = (f"video_size={width}x{height}:pix_fmt=gbrap:time_base=1/1000000:"
            "frame_rate=30/1:pixel_aspect=1/1")
    graph = av.filter.Graph()
    if hasattr(graph, "threads"):
        graph.threads = 1
    left, right = graph.add("buffer", args), graph.add("buffer", args)
    # Décaler le début dans le passé pour demander directement la phase voulue.
    effect = graph.add("xfade", f"transition={kind}:duration=1:offset={-progress:.6f}")
    sink = graph.add("buffersink")
    left.link_to(effect, 0, 0)
    right.link_to(effect, 0, 1)
    effect.link_to(sink)
    graph.configure()
    for node, pixels in ((left, outgoing), (right, incoming)):
        frame = av.VideoFrame.from_ndarray(pixels, format="rgba").reformat(format="gbrap")
        frame.pts, frame.time_base = 0, _TIME_BASE
        node.push(frame)
    return sink.pull().to_ndarray(format="rgba")
