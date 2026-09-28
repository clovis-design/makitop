import pytest

from makitop.media.probe import MediaProbeError, probe
from makitop.model.media import MediaKind


def test_video(video_file):
    media = probe(video_file)
    assert media.kind is MediaKind.VIDEO
    assert (media.width, media.height) == (64, 48)
    assert media.fps == pytest.approx(10)
    assert media.duration == pytest.approx(1, abs=0.2)
    assert media.video_codec == "mpeg4"
    assert media.has_audio
    assert media.channels == 2


def test_audio(audio_file):
    media = probe(audio_file)
    assert media.kind is MediaKind.AUDIO
    assert media.duration == pytest.approx(0.5, abs=0.05)
    assert media.sample_rate == 22050
    assert media.channels == 1
    assert media.width is None


def test_image_avec_accents_dans_le_nom(image_file):
    media = probe(image_file)
    assert media.kind is MediaKind.IMAGE
    assert (media.width, media.height) == (32, 16)
    assert media.duration is None
    assert media.name == "logo été.png"


def test_fichier_introuvable(tmp_path):
    with pytest.raises(MediaProbeError, match="introuvable"):
        probe(tmp_path / "absent.mp4")


def test_extension_non_supportee(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("bonjour")
    with pytest.raises(MediaProbeError, match="non supporté"):
        probe(path)


@pytest.mark.parametrize("name", ["faux.mp4", "faux.png"])
def test_fichier_corrompu(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"pas un vrai media")
    with pytest.raises(MediaProbeError, match="illisible"):
        probe(path)
