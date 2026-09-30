from pathlib import Path

import dearpygui.dearpygui as dpg
import pytest

from makitop.application.projects import ProjectSession
from makitop.storage.recent import RecentProjects
from makitop.ui import main_window, menu_bar
from makitop.ui.dialogs import message, project_file


@pytest.fixture
def context():
    dpg.create_context()
    yield
    dpg.destroy_context()


@pytest.fixture
def session(tmp_path):
    return ProjectSession(RecentProjects(tmp_path / "recent.json"))


def _recent_labels() -> list[str]:
    items = dpg.get_item_children(menu_bar.RECENT_MENU_TAG, 1)
    return [dpg.get_item_label(i) for i in items]


def test_sous_menu_recents(context, tmp_path):
    main_window.build()
    assert _recent_labels() == ["(aucun)"]

    opened = []
    menu_bar.set_recent_projects([tmp_path / "film.makitop"], opened.append)
    assert _recent_labels() == [f"film   ({tmp_path})"]

    item = dpg.get_item_children(menu_bar.RECENT_MENU_TAG, 1)[0]
    dpg.get_item_callback(item)(item, None, None)
    assert opened == [tmp_path / "film.makitop"]


def test_enregistrer_un_nouveau_projet_ouvre_le_dialogue(context, session):
    project_file.create(session)
    project_file.save()
    assert dpg.is_item_shown(project_file.SAVE_DIALOG_TAG)
    assert dpg.get_item_configuration(project_file.SAVE_DIALOG_TAG)["default_filename"] == (
        "Sans titre"
    )


def test_ouverture_ratee_affiche_un_message(context, session, tmp_path):
    project_file.create(session)
    project_file.open_path(tmp_path / "absent.makitop")
    assert dpg.is_item_shown(message.TAG)
    assert dpg.get_value(message.TEXT_TAG) == "Projet introuvable : absent.makitop"


def test_nom_tape_dans_le_dialogue():
    app_data = {"file_name": "film", "file_path_name": "C:/v/film", "selections": {}}
    assert project_file.chosen_path(app_data) == Path("C:/v/film")
    assert project_file.chosen_path({"file_name": "", "selections": {}}) is None
