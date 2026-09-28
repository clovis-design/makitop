import dearpygui.dearpygui as dpg
import pytest

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
    sidebar.select("video_effects")
    visibles = [key for key, _ in media.SECTIONS if dpg.is_item_shown(media.section_tag(key))]
    assert visibles == ["video_effects"]
    assert dpg.get_value(media.TITLE_TAG) == "Effets vidéo"
