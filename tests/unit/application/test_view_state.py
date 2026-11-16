"""État d'affichage (position de lecture, zoom de la timeline) : enregistrement,
réouverture et marquage du projet comme modifié."""

import json

import pytest

from makitop.application.composition import CompositionEditor
from makitop.application.projects import ProjectSession
from makitop.model.media import Media, MediaKind
from makitop.model.project import DEFAULT_TIMELINE_ZOOM, ViewState
from makitop.model.timeline import ImageClip
from makitop.storage import project_file
from makitop.storage.recent import RecentProjects


class FakePlayback:
    """Lecteur réduit à son horloge : suffisant pour l'éditeur, sans décodage."""

    def __init__(self):
        self.time = 0.0

    def set_project(self, project, position=0.0):
        self.time = position

    def seek(self, position):
        self.time = position

    def current_time(self):
        return self.time

    def is_playing(self):
        return False


@pytest.fixture
def editor(tmp_path):
    session = ProjectSession(RecentProjects(tmp_path / "recent.json"))
    return CompositionEditor(session, FakePlayback())


def _image(tmp_path, name):
    return Media(path=tmp_path / name, kind=MediaKind.IMAGE, width=10, height=10)


# --- Modèle et fichier -------------------------------------------------------------------


def test_valeurs_par_defaut():
    assert ViewState() == ViewState(playhead=0.0, timeline_zoom=DEFAULT_TIMELINE_ZOOM)


@pytest.mark.parametrize("kwargs", [{"playhead": -1.0}, {"timeline_zoom": 0}])
def test_valeurs_invalides(kwargs):
    with pytest.raises(ValueError):
        ViewState(**kwargs)


def test_aller_retour_fichier(editor, tmp_path):
    editor.project.view = ViewState(playhead=12.4, timeline_zoom=245)
    project_file.save(editor.project, tmp_path / "p.makitop")
    assert project_file.load(tmp_path / "p.makitop").view == ViewState(12.4, 245)


def test_ancien_projet_sans_etat_d_affichage(editor, tmp_path):
    project_file.save(editor.project, tmp_path / "p.makitop")
    path = tmp_path / "p.makitop"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["view"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert project_file.load(path).view == ViewState()


# --- Éditeur -----------------------------------------------------------------------------


def test_deplacer_la_tete_de_lecture_modifie_le_projet(editor):
    editor.sync_playhead()
    assert not editor.session.dirty  # rien n'a bougé

    editor.seek(3.25)
    editor.sync_playhead()
    assert editor.project.view.playhead == 3.25
    assert editor.session.dirty
    assert editor.session.title.endswith("*")


def test_apercu_d_un_media_seul_ne_touche_pas_au_montage(editor, tmp_path):
    editor.preview_source(_image(tmp_path, "a.png"))
    editor.playback.seek(4.0)
    editor.sync_playhead()
    assert editor.project.view.playhead == 0.0
    assert not editor.session.dirty


def test_zoom_modifie_le_projet(editor):
    editor.set_timeline_zoom(DEFAULT_TIMELINE_ZOOM)
    assert not editor.session.dirty  # même valeur : rien ne change
    editor.set_timeline_zoom(245)
    assert editor.project.view.timeline_zoom == 245
    assert editor.session.dirty


def test_lignes_de_la_timeline_dans_l_ordre_des_pistes_avec_les_images(editor, tmp_path):
    fond = ImageClip(0, _image(tmp_path, "fond.png"), 5.0, track=0)
    logo = ImageClip(0, _image(tmp_path, "logo.png"), 5.0, track=2)
    titre = ImageClip(0, _image(tmp_path, "titre.png"), 5.0, track=1)
    editor.project.timeline.clips = [logo, fond, titre]
    assert editor.rows() == [fond, titre, logo]


def test_reordonner_une_ligne_change_les_pistes(editor, tmp_path):
    fond = ImageClip(0, _image(tmp_path, "fond.png"), 5.0, track=0)
    titre = ImageClip(0, _image(tmp_path, "titre.png"), 5.0, track=1)
    logo = ImageClip(0, _image(tmp_path, "logo.png"), 5.0, track=2)
    editor.project.timeline.clips = [fond, titre, logo]

    editor.reorder_row(fond.id, 2)  # le fond glissé tout en bas : il passe devant

    assert editor.rows() == [titre, logo, fond]
    assert [c.track for c in (titre, logo, fond)] == [0, 1, 2]
    assert editor.session.dirty


def test_reordonner_un_clip_inconnu_ne_fait_rien(editor, tmp_path):
    fond = ImageClip(0, _image(tmp_path, "fond.png"), 5.0, track=0)
    editor.project.timeline.clips = [fond]
    editor.reorder_row("inconnu", 0)
    assert fond.track == 0
    assert not editor.session.dirty
