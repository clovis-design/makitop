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
