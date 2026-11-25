from itertools import combinations

import numpy as np
import pytest

from makitop.ui.panels.timeline import icons


def _icon(name):
    return icons.icon_rgba(name, icons.ICON_SIZE, icons._mask).reshape(16, 16, 4)


@pytest.mark.parametrize("name", icons.NAMES)
def test_icone_taille_et_transparence(name):
    data = icons.icon_rgba(name, icons.ICON_SIZE, icons._mask)
    assert data.shape == (16 * 16 * 4,)
    alpha = data.reshape(16, 16, 4)[..., 3]
    assert alpha.max() == pytest.approx(1)
    assert alpha.min() == 0


def test_icones_distinctes_et_annuler_retablir_miroirs():
    rendered = {name: _icon(name) for name in icons.NAMES}
    for a, b in combinations(icons.NAMES, 2):
        assert not np.array_equal(rendered[a], rendered[b]), (a, b)
    assert np.allclose(rendered["redo"], rendered["undo"][:, ::-1])


def test_icone_inconnue():
    with pytest.raises(KeyError):
        _icon("paint")
