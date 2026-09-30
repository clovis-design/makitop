from pathlib import Path

import pytest

from makitop.model.media import Image, Video
from makitop.model.project import Project


def test_ajout_et_recherche(tmp_path):
    project = Project()
    media = Video(path=tmp_path / "a.mp4", width=1, height=1)
    project.add_media(media)
    assert project.find_media(tmp_path / "a.mp4") is media
    assert project.find_media(tmp_path / "b.mp4") is None


def test_doublon_refuse(tmp_path):
    project = Project()
    project.add_media(Video(path=tmp_path / "a.mp4", width=1, height=1))
    with pytest.raises(ValueError):
        project.add_media(Video(path=tmp_path / "." / "a.mp4", width=1, height=1))


def test_identifiants_uniques():
    a = Image(path=Path("a.png"), width=1, height=1)
    b = Image(path=Path("a.png"), width=1, height=1)
    assert a.id != b.id


def test_remplacer_un_media_garde_sa_place(tmp_path):
    a = Image(path=tmp_path / "a.png", width=1, height=1)
    b = Image(path=tmp_path / "b.png", width=1, height=1)
    project = Project(media=[a, b])
    moved = a.model_copy(update={"path": tmp_path / "ailleurs" / "a.png"})
    project.replace_media(moved)
    assert project.media == [moved, b]
    with pytest.raises(KeyError):
        project.replace_media(Image(path=tmp_path / "c.png", width=1, height=1))


def test_medias_introuvables(tmp_path):
    present = tmp_path / "la.png"
    present.write_bytes(b"x")
    project = Project(
        media=[
            Image(path=present, width=1, height=1),
            Image(path=tmp_path / "parti.png", width=1, height=1),
        ]
    )
    assert [m.name for m in project.missing_media()] == ["parti"]
