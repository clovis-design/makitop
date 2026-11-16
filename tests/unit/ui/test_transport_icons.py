import numpy as np
import pytest

from makitop.ui.panels import transport_icons


@pytest.mark.parametrize("name", transport_icons.NAMES)
def test_icone_taille_et_transparence(name):
    data = transport_icons.icon_rgba(name, 16)
    assert data.shape == (16 * 16 * 4,)
    alpha = data.reshape(16, 16, 4)[..., 3]
    assert alpha.max() == pytest.approx(1)
    assert alpha.min() == 0


def test_icones_distinctes_et_debut_fin_miroirs():
    icons = {n: transport_icons.icon_rgba(n).reshape(16, 16, 4) for n in transport_icons.NAMES}
    assert not np.array_equal(icons["play"], icons["pause"])
    assert np.allclose(icons["end"], icons["start"][:, ::-1])


def test_icone_inconnue():
    with pytest.raises(KeyError):
        transport_icons.icon_rgba("rewind")
