from makitop.ui.layout import MIN_PANEL, SPACING, V_SPACING, compute_layout


def test_barre_et_medias_prennent_toute_la_hauteur():
    layout = compute_layout(1280, 800)
    full_h = layout.preview.height + V_SPACING + layout.timeline.height
    assert layout.sidebar.height == layout.media.height == full_h


def test_timeline_sous_preview_et_proprietes():
    layout = compute_layout(1280, 800)
    assert layout.preview.height == layout.properties.height
    assert layout.timeline.width == layout.preview.width + SPACING + layout.properties.width


def test_preview_plus_large_que_les_cotes():
    layout = compute_layout(1280, 800)
    assert layout.preview.width > layout.media.width
    assert layout.preview.width > layout.properties.width


def test_petite_fenetre_garde_des_tailles_minimales():
    layout = compute_layout(10, 10)
    for size in (layout.media, layout.preview, layout.properties, layout.timeline):
        assert size.width >= MIN_PANEL
        assert size.height >= MIN_PANEL
