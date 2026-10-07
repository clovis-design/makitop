from datetime import datetime
from pathlib import Path

import dearpygui.dearpygui as dpg
import pytest

from makitop.application.projects import ProjectSession
from makitop.model.media import Media, MediaKind
from makitop.storage.recent import RecentProject, RecentProjects
from makitop.ui import home, main_window, screens
from makitop.ui.dialogs import project_file, unsaved_changes


@pytest.fixture
def context():
    dpg.create_context()
    yield
    dpg.destroy_context()


def _click(tag):
    dpg.get_item_callback(tag)(tag, None, None)


def _selectables() -> list[int]:
    found = []

    def walk(item):
        for children in dpg.get_item_children(item).values():
            for child in children:
                if dpg.get_item_type(child) == "mvAppItemType::mvSelectable":
                    found.append(child)
                walk(child)

    walk(home.LIST_TAG)
    return found


# --- Contenu de la page -----------------------------------------------------------------


def test_boutons_nouveau_et_ouvrir(context):
    calls = []
    home.create(on_new=lambda: calls.append("nouveau"), on_open=lambda: calls.append("ouvrir"))
    _click(home.NEW_BUTTON)
    _click(home.OPEN_BUTTON)
    assert calls == ["nouveau", "ouvrir"]


def test_liste_vide(context):
    home.create(on_new=lambda: None, on_open=lambda: None)
    assert _selectables() == []
    texts = [dpg.get_value(i) for i in dpg.get_item_children(home.LIST_TAG, 1)]
    assert texts and texts[0].startswith("Aucun projet")


def test_liste_des_projets_et_clic(context):
    home.create(on_new=lambda: None, on_open=lambda: None)
    opened = []
    projects = [
        RecentProject(Path("C:/films/Vacances.makitop"), datetime(2026, 10, 7, 14, 30)),
        RecentProject(Path("C:/films/Mariage.makitop"), datetime(2026, 9, 1, 8, 0)),
    ]
    home.set_projects(projects, opened.append)

    rows = _selectables()
    assert [dpg.get_item_label(r) for r in rows] == ["Vacances", "Mariage"]
    _click(rows[1])
    assert opened == [Path("C:/films/Mariage.makitop")]

    home.set_projects(projects[:1], opened.append)  # la liste est remplacée, pas complétée
    assert len(_selectables()) == 1


@pytest.mark.parametrize(
    ("when", "expected"),
    [
        (None, "—"),
        (datetime(2026, 10, 7, 9, 5), "Aujourd'hui à 09:05"),
        (datetime(2026, 10, 6, 23, 59), "Hier à 23:59"),
        (datetime(2026, 10, 4, 12, 0), "Il y a 3 jours"),
        (datetime(2026, 9, 30, 12, 0), "30/09/2026"),
    ],
)
def test_format_derniere_utilisation(when, expected):
    assert home.format_last_used(when, now=datetime(2026, 10, 7, 16, 0)) == expected


# --- Passage accueil <-> éditeur --------------------------------------------------------


@pytest.fixture
def app(context, tmp_path):
    """Assemblage minimal : accueil, éditeur et session, branchés comme dans app.py."""
    session = ProjectSession(RecentProjects(tmp_path / "recent.json"))
    main_window.build()
    home.create(on_new=project_file.new_project, on_open=project_file.open_dialog)
    project_file.create(session)
    session.on_project_changed(lambda project: screens.show_editor())
    screens.show_home()
    return session


def test_accueil_affiche_au_lancement(app):
    assert screens.home_shown()
    assert not dpg.is_item_shown(main_window.ROOT)


def test_nouveau_projet_ouvre_l_editeur(app):
    _click(home.NEW_BUTTON)
    assert not screens.home_shown()
    assert dpg.is_item_shown(main_window.ROOT)


def test_ouvrir_un_projet_de_la_liste_ouvre_l_editeur(app, tmp_path):
    app.save_as(tmp_path / "Film")
    screens.show_home()
    home.set_projects(app.recent.entries(), project_file.open_path)

    _click(_selectables()[0])
    assert not screens.home_shown()
    assert app.path == tmp_path / "Film.makitop"


def test_projet_illisible_reste_sur_l_accueil(app, tmp_path):
    (tmp_path / "casse.makitop").write_text("{", encoding="utf-8")
    project_file.open_path(tmp_path / "casse.makitop")
    assert screens.home_shown()


def test_fermer_le_projet_revient_a_l_accueil(app, tmp_path):
    _click(home.NEW_BUTTON)
    project_file.close_project(screens.show_home)
    assert screens.home_shown()


def test_fermer_un_projet_modifie_demande_confirmation(app, tmp_path):
    _click(home.NEW_BUTTON)
    app.project.add_media(Media(path=tmp_path / "a.png", kind=MediaKind.IMAGE))
    app.mark_dirty()

    project_file.close_project(screens.show_home)
    assert dpg.is_item_shown(unsaved_changes.TAG)
    assert not screens.home_shown()

    _click(unsaved_changes.DISCARD_BUTTON)
    assert screens.home_shown()
    assert app.project.media == []
