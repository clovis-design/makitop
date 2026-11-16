import numpy as np
import pytest
from PIL import Image

from makitop.engine.effects import video
from makitop.engine.timeline import TimelineRenderer
from makitop.media.probe import probe
from makitop.model.effects import CATALOG, Effect
from makitop.model.project import Project
from makitop.model.timeline import ImageClip, Timeline


def sample(channels=3):
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, (36, 64, channels), dtype=np.uint8)


def fx(kind, amount=None):
    return (Effect(kind, CATALOG[kind].default if amount is None else amount),)


@pytest.mark.parametrize("channels", [3, 4])
@pytest.mark.parametrize("kind", list(CATALOG))
def test_forme_et_type_conserves(kind, channels):
    out = video.apply(sample(channels), fx(kind), 0.5, 2.0, 3)
    assert out.dtype == np.uint8
    assert out.shape[:2] == (36, 64)
    assert out.shape[2] in (3, 4)


def test_sans_effet_image_inchangee():
    image = sample()
    assert video.apply(image, (), 0, 1, 0) is image


def test_filtres():
    image = sample()
    bw = video.apply(image, fx("bw"), 0, 1, 0).astype(int)
    assert (np.abs(bw[..., 0] - bw[..., 1]) <= 1).all()
    assert (np.abs(bw[..., 1] - bw[..., 2]) <= 1).all()
    twice = video.apply(video.apply(image, fx("invert"), 0, 1, 0), fx("invert"), 0, 1, 0)
    np.testing.assert_array_equal(twice, image)
    np.testing.assert_array_equal(video.apply(image, fx("mirror"), 0, 1, 0), image[:, ::-1])


def test_fondus_utilisent_la_transparence():
    image = sample()
    start = video.apply(image, fx("fade_in", 1), 0, 4, 0)
    assert start.shape[2] == 4 and not start[..., 3].any()
    assert (video.apply(image, fx("fade_in", 1), 2, 4, 0)[..., 3] == 255).all()
    assert video.apply(image, fx("fade_out", 1), 3.5, 4, 0)[..., 3].max() == 128


def test_grain_deterministe():
    image = sample()
    a = video.apply(image, fx("grain"), 0, 1, 5)
    np.testing.assert_array_equal(a, video.apply(image, fx("grain"), 0, 1, 5))
    assert not np.array_equal(a, video.apply(image, fx("grain"), 0, 1, 6))


def test_rendu_avec_effets_et_cache_par_instant(tmp_path):
    path = tmp_path / "rouge.png"
    Image.new("RGB", (64, 48), (255, 0, 0)).save(path)
    media = probe(path)
    clip = ImageClip(0, media, 2, effects=fx("bw"))
    project = Project(media=[media], timeline=Timeline(clips=[clip]))
    renderer = TimelineRenderer(64, 48)
    try:
        frame = renderer.render(project, 0).astype(int)
        assert (frame[..., 0] == frame[..., 2]).all() and frame.mean() > 50
        project.timeline = Timeline(clips=[ImageClip(0, media, 2, effects=fx("fade_in", 1))])
        early, late = renderer.render(project, 3), renderer.render(project, 30)
        assert early.mean() < late.mean()
    finally:
        renderer.close()
