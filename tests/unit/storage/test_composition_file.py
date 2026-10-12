import json

import pytest

from makitop.media.probe import probe
from makitop.model.composition import Transform
from makitop.model.project import Project
from makitop.model.timeline import ImageClip, MediaClip, Timeline
from makitop.storage.project_file import ProjectFileError, load, save


def test_composition_round_trip(video_file, image_file, tmp_path):
    video, photo = probe(video_file), probe(image_file)
    project = Project(canvas_format="9:16", media=[video, photo], timeline=Timeline(fps=25, clips=[
        MediaClip(2, video, 0.1, 0.9, track=2, volume=0.4, muted=True,
                  transform=Transform(x=0.25, width=0.5, crop_left=0.1)),
        ImageClip(0, photo, 8, track=0, transform=Transform(y=0.3, height=0.4)),
    ]))
    path = tmp_path / "composition.makitop"
    save(project, path)
    assert load(path) == project
    assert json.loads(path.read_text())["version"] == 3


@pytest.mark.parametrize("legacy_shape", ["list", "dict"])
def test_v2_migration_preserves_clips(video_file, tmp_path, legacy_shape):
    video = probe(video_file)
    path = tmp_path / "legacy.makitop"
    save(Project(media=[video], timeline=Timeline(clips=[MediaClip(0, video, 0.2, 0.8)])), path)
    data = json.loads(path.read_text())
    data["version"] = 2
    del data["canvas_format"]
    del data["fps"]
    clip = data["timeline"][0]
    for key in ("track", "transform", "volume", "muted"):
        del clip[key]
    if legacy_shape == "dict":
        del clip["clip_type"]
        clip["source_in"] = clip.pop("source_start")
        clip["source_out"] = clip.pop("source_end")
        data["timeline"] = {"clips": [clip], "fps": 24}
    path.write_text(json.dumps(data))
    loaded = load(path)
    assert loaded.timeline.clips[0].source_start == 0.2
    assert loaded.timeline.clips[0].transform == Transform()
    assert loaded.timeline.clips[0].volume == 1
    assert loaded.canvas_format == "16:9"
    assert loaded.timeline.fps == (24 if legacy_shape == "dict" else 30)


def test_invalid_geometry_is_reported_as_corrupt_project(image_file, tmp_path):
    media = probe(image_file)
    path = tmp_path / "bad.makitop"
    save(Project(media=[media], timeline=Timeline(clips=[ImageClip(0, media, 2)])), path)
    data = json.loads(path.read_text())
    data["timeline"][0]["transform"]["crop_left"] = 1
    path.write_text(json.dumps(data))
    with pytest.raises(ProjectFileError, match="corrompu"):
        load(path)
