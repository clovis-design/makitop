import pytest

from makitop.media.probe import probe
from makitop.model.effects import CATALOG, CATEGORIES, Effect
from makitop.model.timeline import ImageClip


def test_catalogue_complet_et_valeurs_par_defaut_valides():
    assert {spec.category for spec in CATALOG.values()} == set(CATEGORIES)
    for kind, spec in CATALOG.items():
        assert spec.min <= spec.default <= spec.max
        assert Effect(kind, spec.default).spec is spec


@pytest.mark.parametrize("kind, amount", [
    ("inconnu", 1), ("bw", 1.5), ("brightness", -2), ("fade_in", 0), ("blur", float("nan")),
])
def test_effet_invalide(kind, amount):
    with pytest.raises(ValueError):
        Effect(kind, amount)


def test_clip_refuse_des_effets_invalides(image_file):
    media = probe(image_file)
    assert ImageClip(0, media, 2, effects=(Effect("bw", 1),)).effects[0].kind == "bw"
    with pytest.raises(ValueError):
        ImageClip(0, media, 2, effects=("bw",))
    with pytest.raises(ValueError):
        ImageClip(0, media, 2, effects=[Effect("bw", 1)])
