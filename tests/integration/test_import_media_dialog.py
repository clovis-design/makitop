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


def test_champ_nom_vide_par_defaut(context):
    import_media.create(on_files_selected=lambda paths: None)
    assert dpg.get_item_configuration(import_media.DIALOG_TAG)["default_filename"] == ""


def test_fichiers_cliques_prioritaires():
    app_data = {
        "file_name": "a.mp4",
        "file_path_name": "C:/v/a.mp4",
        "selections": {"a.mp4": "C:/v/a.mp4", "b.png": "C:/v/b.png"},
    }
    assert import_media.selected_paths(app_data) == [Path("C:/v/a.mp4"), Path("C:/v/b.png")]


def test_nom_tape_a_la_main():
    # Format réellement renvoyé par Dear PyGui quand on tape un nom sans cliquer de fichier.
    app_data = {"file_name": "tape.mp4", "file_path_name": "C:/v/tape.mp4", "selections": {}}
    assert import_media.selected_paths(app_data) == [Path("C:/v/tape.mp4")]


def test_rien_de_choisi():
    assert import_media.selected_paths({"file_name": " ", "selections": {}}) == []


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
