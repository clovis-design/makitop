import dearpygui.dearpygui as dpg
import pytest

from makitop.media.probe import probe
from makitop.ui import main_window
from makitop.ui.panels import media, preview, properties, sidebar, timeline


@pytest.fixture
def context():
    dpg.create_context()
    yield
    dpg.destroy_context()


def test_build_cree_toutes_les_zones(context):
    main_window.build()
    for tag in (
        main_window.ROOT,
        sidebar.TAG,
        media.TAG,
        preview.TAG,
        properties.TAG,
        timeline.TAG,
    ):
        assert dpg.does_item_exist(tag)


def test_resize_applique_les_tailles(context):
    main_window.build()
    main_window.resize(1280, 800)
    assert dpg.get_item_height(media.TAG) > dpg.get_item_height(preview.TAG)
    assert dpg.get_item_width(timeline.TAG) > dpg.get_item_width(preview.TAG)


def test_une_seule_section_media_visible(context):
    main_window.build()
    sidebar.select("transitions")
    visibles = [key for key, _ in media.SECTIONS if dpg.is_item_shown(media.section_tag(key))]
    assert visibles == ["transitions"]
    assert dpg.get_value(media.TITLE_TAG) == "Transitions"


def test_selection_media_apres_reconstruction(context, video_file, monkeypatch):
    selected = []
    main_window.build(on_media_selected=selected.append)
    # La mesure des polices nécessite normalement une fenêtre affichée.
    monkeypatch.setattr(dpg, "get_text_size", lambda text: (len(text) * 8, 16))
    imported = probe(video_file)
    media.add_media(imported)
    media._rebuild(2)
    draw_tag = f"media_draw_{imported.id}"
    handler = dpg.get_item_info(draw_tag)["handlers"]
    click_handler = dpg.get_item_children(handler, 1)[0]
    callback = dpg.get_item_callback(click_handler)
    callback(click_handler, (dpg.mvMouseButton_Left, dpg.get_alias_id(draw_tag)))
    assert selected == [imported]
