import json
from pathlib import Path

import pytest

from makitop.model.media import Audio, Image, Video
from makitop.model.project import Project
from makitop.storage import project_file
from makitop.storage.project_file import ProjectFileError


def _project(tmp_path: Path) -> Project:
    return Project(
        name="Vacances",
        media=[
            Video(path=tmp_path / "rushs" / "plage.mp4", width=1920, height=1080, fps=25.0),
            Audio(path=tmp_path / "musique été.mp3", audio_codec="mp3", duration=12.5),
            Image(path=Path("D:/ailleurs/logo.png").absolute(), width=32, height=16),
        ],
    )


def test_aller_retour_conserve_tout(tmp_path):
    project = _project(tmp_path)
    path = tmp_path / "vacances.makitop"
    project_file.save(project, path)
    loaded = project_file.load(path)

    assert loaded.name == "Vacances"
    assert [type(m) for m in loaded.media] == [Video, Audio, Image]
    assert loaded.media == project.media  # mêmes champs, mêmes identifiants


def test_chemins_relatifs_dans_le_dossier_du_projet(tmp_path):
    project_file.save(_project(tmp_path), tmp_path / "p.makitop")
    data = json.loads((tmp_path / "p.makitop").read_text(encoding="utf-8"))
    paths = [m["path"] for m in data["media"]]

    assert paths[0] == "rushs/plage.mp4"
    assert paths[1] == "musique été.mp3"
    assert Path(paths[2]).is_absolute()


def test_dossier_du_projet_deplace(tmp_path):
    old = tmp_path / "ancien"
    old.mkdir()
    project_file.save(_project(old), old / "p.makitop")
    new = old.rename(tmp_path / "nouveau")

    loaded = project_file.load(new / "p.makitop")
    assert loaded.media[0].path == new / "rushs" / "plage.mp4"


def test_projet_vide(tmp_path):
    project_file.save(Project(name="Vide"), tmp_path / "v.makitop")
    assert project_file.load(tmp_path / "v.makitop").media == []


def test_ecrasement_sans_fichier_temporaire_restant(tmp_path):
    path = tmp_path / "p.makitop"
    project_file.save(Project(name="A"), path)
    project_file.save(Project(name="B"), path)
    assert project_file.load(path).name == "B"
    assert list(tmp_path.iterdir()) == [path]


def test_introuvable(tmp_path):
    with pytest.raises(ProjectFileError, match="introuvable"):
        project_file.load(tmp_path / "absent.makitop")


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("pas du json", "illisible"),
        ('{"format": "autre", "version": 1}', "pas un projet Makitop"),
        ('{"format": "makitop", "version": 99}', "plus récente"),
        ('{"format": "makitop", "version": 1, "media": [{"type": "inconnu"}]}', "corrompu"),
        ('{"format": "makitop", "version": 1, "media": [{"type": "video"}]}', "corrompu"),
    ],
)
def test_fichiers_invalides(tmp_path, content, match):
    path = tmp_path / "p.makitop"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ProjectFileError, match=match):
        project_file.load(path)
