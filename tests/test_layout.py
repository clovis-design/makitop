from makitop.ui.layout import MIN_PANEL, compute_layout


def test_zones_du_haut_ont_la_meme_hauteur():
    layout = compute_layout(1280, 800)
    assert layout.media.height == layout.preview.height == layout.properties.height


def test_preview_plus_large_que_les_cotes():
    layout = compute_layout(1280, 800)
    assert layout.preview.width > layout.media.width
    assert layout.media.width == layout.properties.width


def test_petite_fenetre_garde_des_tailles_minimales():
    layout = compute_layout(10, 10)
    for size in (layout.media, layout.preview, layout.properties, layout.timeline):
        assert size.width >= MIN_PANEL
        assert size.height >= MIN_PANEL
