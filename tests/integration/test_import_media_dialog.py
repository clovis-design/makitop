from pathlib import Path

import dearpygui.dearpygui as dpg
import pytest

from makitop.ui import main_window, menu_bar
from makitop.ui.dialogs import import_media


@pytest.fixture
def context():
    dpg.create_context()
    yield
    dpg.destroy_context()


def test_menu_importer_actif_uniquement_avec_une_action(context):
    main_window.build(actions={menu_bar.IMPORT_MEDIA: lambda: None})
    assert dpg.get_item_configuration(menu_bar.item_tag(menu_bar.IMPORT_MEDIA))["enabled"]
    assert not dpg.get_item_configuration(menu_bar.item_tag("Exporter..."))["enabled"]


def test_dialogue_cree_puis_ouvert(context):
    import_media.create(on_files_selected=lambda paths: None)
    assert not dpg.is_item_shown(import_media.DIALOG_TAG)
    import_media.open_dialog()
    assert dpg.is_item_shown(import_media.DIALOG_TAG)


def test_erreurs_affichees_puis_videes(context):
    import_media.create(on_files_selected=lambda paths: None)
    import_media.show_error(Path("a.txt"), "Format non supporté : .txt")
    import_media.show_error(Path("b.mp4"), "Fichier illisible : b.mp4")

    assert dpg.is_item_shown(import_media.ERRORS_TAG)
    items = dpg.get_item_children(import_media.ERRORS_LIST_TAG, 1)
    assert [dpg.get_value(i) for i in items] == [
        "Format non supporté : .txt",
        "Fichier illisible : b.mp4",
    ]

    import_media._close_errors()
    assert not dpg.is_item_shown(import_media.ERRORS_TAG)
    assert dpg.get_item_children(import_media.ERRORS_LIST_TAG, 1) == []
