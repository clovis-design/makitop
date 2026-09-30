import pytest

from makitop.application.projects import ProjectSession
from makitop.model.media import Image
from makitop.storage.project_file import ProjectFileError
from makitop.storage.recent import RecentProjects


@pytest.fixture
def session(tmp_path):
    return ProjectSession(RecentProjects(tmp_path / "config" / "recent.json"))


def _add_image(session, tmp_path):
    session.project.add_media(Image(path=tmp_path / "a.png", width=1, height=1))
    session.mark_dirty()


def test_nouveau_projet_non_enregistre(session):
    assert session.path is None
    assert not session.dirty
    assert session.title == "Sans titre"


def test_modification_puis_enregistrer_sous(session, tmp_path):
    _add_image(session, tmp_path)
    assert session.title == "Sans titre *"

    session.save_as(tmp_path / "Mon film")

    assert session.path == tmp_path / "Mon film.makitop"
    assert session.path.is_file()
    assert not session.dirty
    assert session.title == "Mon film"
    assert session.recent.paths() == [session.path]


def test_enregistrer_sans_fichier_refuse(session):
    with pytest.raises(ValueError):
        session.save()


def test_ouvrir_restaure_les_imports(session, tmp_path):
    _add_image(session, tmp_path)
    session.save_as(tmp_path / "p.makitop")
    session.new()
    assert session.project.media == []

    changed = []
    session.on_project_changed(changed.append)
    session.open(tmp_path / "p.makitop")

    assert [m.path for m in session.project.media] == [tmp_path / "a.png"]
    assert changed == [session.project]
    assert not session.dirty


def test_ouverture_ratee_garde_le_projet_courant(session, tmp_path):
    _add_image(session, tmp_path)
    before = session.project
    (tmp_path / "casse.makitop").write_text("{", encoding="utf-8")

    with pytest.raises(ProjectFileError):
        session.open(tmp_path / "casse.makitop")
    assert session.project is before
    assert session.dirty


def test_ecouteurs_d_etat(session, tmp_path):
    calls = []
    session.on_state_changed(lambda: calls.append(session.title))
    _add_image(session, tmp_path)
    session.mark_dirty()  # déjà modifié : pas de nouvel appel
    session.save_as(tmp_path / "p")
    assert calls == ["Sans titre *", "p"]


def _missing_project(session, tmp_path, image_file, audio_file):
    """Projet enregistré dont les deux médias sont ensuite déplacés dans « deplaces/ »."""
    from makitop.media.probe import probe

    image, audio = probe(image_file), probe(audio_file)
    session.project.add_media(image)
    session.project.add_media(audio)
    moved = tmp_path / "deplaces"
    moved.mkdir()
    image_file.rename(moved / image_file.name)
    audio_file.rename(moved / audio_file.name)
    return image, audio, moved


def test_relier_retrouve_aussi_les_voisins(session, tmp_path, image_file, audio_file):
    image, audio, moved = _missing_project(session, tmp_path, image_file, audio_file)
    assert len(session.project.missing_media()) == 2
    notified = []
    session.on_media_relinked(notified.append)

    relinked = session.relink(image, moved / image_file.name)

    assert [m.id for m in relinked] == [image.id, audio.id]  # identifiants conservés
    assert session.project.missing_media() == []
    assert session.project.media[0].path == moved / image_file.name
    assert notified == [relinked]
    assert session.dirty


def test_relier_a_un_fichier_d_un_autre_type_refuse(session, tmp_path, image_file, audio_file):
    from makitop.media.probe import MediaProbeError

    image, _, moved = _missing_project(session, tmp_path, image_file, audio_file)
    with pytest.raises(MediaProbeError, match="n'est pas une image"):
        session.relink(image, moved / audio_file.name)
    assert len(session.project.missing_media()) == 2
