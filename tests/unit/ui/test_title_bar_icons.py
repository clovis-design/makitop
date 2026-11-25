from itertools import combinations

import numpy as np
import pytest

from makitop.ui import title_bar


def _icon(name):
    size = title_bar.ICON_SIZE
    return title_bar.icon_rgba(name, size, title_bar._mask).reshape(size, size, 4)


@pytest.mark.parametrize("name", title_bar.NAMES)
def test_icone_taille_et_transparence(name):
    alpha = _icon(name)[..., 3]
    assert alpha.max() == pytest.approx(1)
    assert alpha.min() == 0


def test_icones_distinctes_et_fermer_symetrique():
    rendered = {name: _icon(name) for name in title_bar.NAMES}
    for a, b in combinations(title_bar.NAMES, 2):
        assert not np.array_equal(rendered[a], rendered[b]), (a, b)
    assert np.allclose(rendered["close"], rendered["close"][:, ::-1])


def test_icone_inconnue():
    with pytest.raises(KeyError):
        _icon("help")
