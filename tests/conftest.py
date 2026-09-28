"""Petits médias générés à la volée (rien de binaire dans le dépôt)."""

from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PIL import Image


@pytest.fixture
def video_file(tmp_path: Path) -> Path:
    """Vidéo MP4 de 1 s, 64x48 à 10 i/s, avec une piste audio stéréo."""
    path = tmp_path / "clip.mp4"
    with av.open(str(path), "w") as container:
        video = container.add_stream("mpeg4", rate=10)
        video.width, video.height, video.pix_fmt = 64, 48, "yuv420p"
        audio = container.add_stream("aac", rate=44100)
        audio.layout = "stereo"

        for i in range(10):
            pixels = np.full((48, 64, 3), i * 20, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            container.mux(video.encode(frame))
        container.mux(video.encode())

        samples = np.zeros((2, 1024), dtype=np.float32)
        for i in range(44):
            frame = av.AudioFrame.from_ndarray(samples, format="fltp", layout="stereo")
            frame.sample_rate = 44100
            frame.pts = i * 1024
            frame.time_base = Fraction(1, 44100)
            container.mux(audio.encode(frame))
        container.mux(audio.encode())
    return path


@pytest.fixture
def audio_file(tmp_path: Path) -> Path:
    """WAV mono de 0,5 s à 22 050 Hz."""
    path = tmp_path / "son.wav"
    with av.open(str(path), "w") as container:
        stream = container.add_stream("pcm_s16le", rate=22050)
        stream.layout = "mono"
        samples = np.zeros((1, 11025), dtype=np.int16)
        frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
        frame.sample_rate = 22050
        container.mux(stream.encode(frame))
        container.mux(stream.encode())
    return path


@pytest.fixture
def image_file(tmp_path: Path) -> Path:
    """PNG 32x16 dont le nom contient un espace et un accent."""
    path = tmp_path / "logo été.png"
    Image.new("RGB", (32, 16), "red").save(path)
    return path
