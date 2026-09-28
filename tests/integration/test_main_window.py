import dearpygui.dearpygui as dpg
import pytest

from makitop.ui import main_window
from makitop.ui.panels import media, preview, properties, timeline


@pytest.fixture
def context():
    dpg.create_context()
    yield
    dpg.destroy_context()


def test_build_cree_toutes_les_zones(context):
    main_window.build()
    for tag in (main_window.ROOT, media.TAG, preview.TAG, properties.TAG, timeline.TAG):
        assert dpg.does_item_exist(tag)


def test_resize_applique_les_tailles(context):
    main_window.build()
    main_window.resize(1280, 800)
    assert dpg.get_item_width(timeline.TAG) > dpg.get_item_width(preview.TAG)
