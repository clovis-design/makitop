import dearpygui.dearpygui as dpg
import pytest

from makitop.application.projects import ProjectSession
from makitop.media.probe import probe
from makitop.model.media import Media, MediaKind
from makitop.storage.recent import RecentProjects
from makitop.ui.dialogs import message, missing_media, project_file, unsaved_changes


@pytest.fixture
def session(tmp_path):
    dpg.create_context()
    session = ProjectSession(RecentProjects(tmp_path / "recent.json"))
    project_file.create(session)
    yield session
    dpg.destroy_context()


def _modify(session, tmp_path):
    session.project.add_media(Media(path=tmp_path / "a.png", kind=MediaKind.IMAGE))
    session.mark_dirty()


def _click(tag):
    dpg.get_item_callback(tag)(tag, None, None)


# --- Modifications non enregistrées ---------------------------------------------------


def test_sans_modification_pas_de_question(session):
    calls = []
    unsaved_changes.confirm(lambda: calls.append("fait"))
    assert calls == ["fait"]
    assert not dpg.is_item_shown(unsaved_changes.TAG)


def test_ne_pas_enregistrer(session, tmp_path):
    _modify(session, tmp_path)
    project_file.new_project()
    assert dpg.is_item_shown(unsaved_changes.TAG)
    assert session.project.media  # rien n'est encore fait

    _click(unsaved_changes.DISCARD_BUTTON)
    assert not dpg.is_item_shown(unsaved_changes.TAG)
    assert session.project.media == []


def test_annuler(session, tmp_path):
    _modify(session, tmp_path)
    project_file.new_project()
    _click(unsaved_changes.CANCEL_BUTTON)
    assert session.project.media
    assert session.dirty


def test_enregistrer_un_projet_deja_enregistre_puis_continuer(session, tmp_path):
    session.save_as(tmp_path / "p.makitop")
    _modify(session, tmp_path)
    project_file.new_project()

    _click(unsaved_changes.SAVE_BUTTON)

    assert session.project.media == []  # nouveau projet créé après l'enregistrement
    assert len(project_file_load(tmp_path / "p.makitop").media) == 1


def test_enregistrer_un_projet_jamais_enregistre_passe_par_le_dialogue(session, tmp_path):
    _modify(session, tmp_path)
    project_file.new_project()
    _click(unsaved_changes.SAVE_BUTTON)
    assert dpg.is_item_shown(project_file.SAVE_DIALOG_TAG)
    assert session.project.media  # on attend le choix de l'emplacement

    project_file.save_as(tmp_path / "choisi")  # ce que fait le dialogue sur OK

    assert (tmp_path / "choisi.makitop").is_file()
    assert session.project.media == []


def test_dialogue_d_enregistrement_annule_ne_continue_pas(session, tmp_path):
    _modify(session, tmp_path)
    project_file.new_project()
    _click(unsaved_changes.SAVE_BUTTON)
    project_file._on_save_cancelled()  # bouton « Cancel » du dialogue

    project_file.save_as(tmp_path / "plus_tard")  # un « Enregistrer sous » ultérieur
    assert session.project.media  # ne déclenche pas le « nouveau projet » oublié


def test_quitter(session, tmp_path, monkeypatch):
    stopped = []
    monkeypatch.setattr(dpg, "stop_dearpygui", lambda: stopped.append(True))
    project_file.quit_app()
    assert stopped == [True]

    stopped.clear()
    _modify(session, tmp_path)
    project_file.quit_app()
    assert stopped == []
    _click(unsaved_changes.DISCARD_BUTTON)
    assert stopped == [True]


def project_file_load(path):
    from makitop.storage import project_file as storage

    return storage.load(path)


# --- Médias introuvables ---------------------------------------------------------------


def test_ouverture_signale_les_medias_introuvables(session, tmp_path, image_file):
    session.project.add_media(probe(image_file))
    session.save_as(tmp_path / "p.makitop")
    moved = tmp_path / "deplaces"
    moved.mkdir()
    image_file.rename(moved / image_file.name)

    project_file.open_path(tmp_path / "p.makitop")
    assert dpg.is_item_shown(missing_media.TAG)

    missing_media.relink(session.project.media[0], moved / image_file.name)
    assert not dpg.is_item_shown(missing_media.TAG)
    assert dpg.get_value(message.TEXT_TAG) == "Tous les médias ont été retrouvés."
    assert session.project.missing_media() == []


def test_ouverture_sans_media_manquant_n_affiche_rien(session, tmp_path, image_file):
    session.project.add_media(probe(image_file))
    session.save_as(tmp_path / "p.makitop")
    project_file.open_path(tmp_path / "p.makitop")
    assert not dpg.is_item_shown(missing_media.TAG)


def test_relier_a_un_mauvais_fichier_affiche_l_erreur(session, tmp_path, image_file, audio_file):
    session.project.add_media(Media(path=tmp_path / "parti.png", kind=MediaKind.IMAGE))
    missing_media.show()
    missing_media.relink(session.project.media[0], audio_file)
    assert dpg.get_value(message.TEXT_TAG) == "son.wav n'est pas une image."
    assert dpg.is_item_shown(missing_media.TAG)
