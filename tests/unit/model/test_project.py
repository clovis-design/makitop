from dataclasses import replace
from pathlib import Path

import pytest

from makitop.model.media import Media, MediaKind
from makitop.model.project import Project


def test_ajout_et_recherche(tmp_path):
    project = Project()
    media = Media(path=tmp_path / "a.mp4", kind=MediaKind.VIDEO)
    project.add_media(media)
    assert project.find_media(tmp_path / "a.mp4") is media
    assert project.find_media(tmp_path / "b.mp4") is None


def test_doublon_refuse(tmp_path):
    project = Project()
    project.add_media(Media(path=tmp_path / "a.mp4", kind=MediaKind.VIDEO))
    with pytest.raises(ValueError):
        project.add_media(Media(path=tmp_path / "." / "a.mp4", kind=MediaKind.VIDEO))


def test_identifiants_uniques():
    a = Media(path=Path("a.png"), kind=MediaKind.IMAGE)
    b = Media(path=Path("a.png"), kind=MediaKind.IMAGE)
    assert a.id != b.id


def test_remplacer_un_media_garde_sa_place(tmp_path):
    a = Media(path=tmp_path / "a.png", kind=MediaKind.IMAGE)
    b = Media(path=tmp_path / "b.png", kind=MediaKind.IMAGE)
    project = Project(media=[a, b])
    moved = replace(a, path=tmp_path / "ailleurs" / "a.png")
    project.replace_media(moved)
    assert project.media == [moved, b]
    with pytest.raises(KeyError):
        project.replace_media(Media(path=tmp_path / "c.png", kind=MediaKind.IMAGE))


def test_medias_introuvables(tmp_path):
    present = tmp_path / "la.png"
    present.write_bytes(b"x")
    project = Project(
        media=[
            Media(path=present, kind=MediaKind.IMAGE),
            Media(path=tmp_path / "parti.png", kind=MediaKind.IMAGE),
        ]
    )
    assert [m.name for m in project.missing_media()] == ["parti.png"]
