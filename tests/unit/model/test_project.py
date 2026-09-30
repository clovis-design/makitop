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
