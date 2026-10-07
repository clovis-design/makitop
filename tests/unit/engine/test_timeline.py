import av
import numpy as np
import pytest

from makitop.engine.cache import FrameCache
from makitop.engine.timeline import TimelineRenderer
from makitop.media.probe import probe
from makitop.model.project import Project
from makitop.model.timeline import Clip, Timeline
from makitop.storage import project_file


def test_split_remove_and_save_preserve_source_mapping(video_file, tmp_path):
    media = probe(video_file)
    project = Project(media=[media])
    project.timeline.append(media.id, 0, 0.9)
    project.timeline.split(0.3)
    project.timeline.split(0.6)
    project.timeline.remove(project.timeline.clips[1].id)
    assert project.timeline.duration == pytest.approx(0.6)
    assert project.timeline.clips[1].source_in == pytest.approx(0.6)
    path = tmp_path / "edit.makitop"
    project_file.save(project, path)
    loaded = project_file.load(path)
    assert loaded.timeline == project.timeline
    renderer = TimelineRenderer(64, 48)
    try:
        assert renderer.render(loaded, 0).mean() < 5
        # À 0,3 s dans le montage, le passage supprimé est sauté : source 0,6 s.
        assert renderer.render(loaded, 9).mean() == pytest.approx(120, abs=5)
        # Retour arrière : le décodeur doit se repositionner.
        assert renderer.render(loaded, 3).mean() == pytest.approx(20, abs=5)
    finally:
        renderer.close()


def test_hold_source_frame_until_next_timestamp(video_file):
    media = probe(video_file)
    project = Project(media=[media], timeline=Timeline([Clip(media.id, 0, 0.9, 0)]))
    renderer = TimelineRenderer(64, 48)
    try:
        values = [renderer.render(project, i).mean() for i in range(7)]
        assert values[:3] == pytest.approx([0, 0, 0], abs=5)
        assert values[3:6] == pytest.approx([20, 20, 20], abs=5)
        assert values[6] == pytest.approx(40, abs=5)
    finally:
        renderer.close()


def test_gap_is_black_and_edits_do_not_reuse_wrong_cache(video_file):
    media = probe(video_file)
    project = Project(media=[media], timeline=Timeline([Clip(media.id, 0.5, 0.9, 0.2)]))
    renderer = TimelineRenderer(64, 48)
    try:
        assert not renderer.render(project, 0).any()
        old = renderer.render(project, 6)
        assert renderer.render(project, 6) is old
        project.timeline = Timeline([Clip(media.id, 0.1, 0.5, 0.2)])
        assert renderer.render(project, 6).mean() < old.mean() - 50
    finally:
        renderer.close()


def test_frame_cache_is_bounded_and_lru():
    cache = FrameCache(max_bytes=24)
    for i in range(2):
        cache.put(i, np.zeros((2, 2, 3), dtype=np.uint8))
    cache.get(0)
    cache.put(2, np.zeros((2, 2, 3), dtype=np.uint8))
    assert cache.get(1) is None
    assert cache.get(0) is not None
    assert cache.size == 24


def test_cut_switches_to_another_file(video_file, tmp_path):
    other = tmp_path / "other.mp4"
    with av.open(str(other), "w") as container:
        stream = container.add_stream("mpeg4", rate=10)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for _ in range(10):
            frame = av.VideoFrame.from_ndarray(
                np.full((48, 64, 3), 220, dtype=np.uint8), format="rgb24"
            )
            container.mux(stream.encode(frame))
        container.mux(stream.encode())
    a, b = probe(video_file), probe(other)
    project = Project(media=[a, b])
    project.timeline.append(a.id, 0, 0.3)
    project.timeline.append(b.id, 0.2, 0.5)
    renderer = TimelineRenderer(64, 48)
    try:
        assert renderer.render(project, 8).mean() < 50
        assert renderer.render(project, 9).mean() > 210
        assert renderer.render(project, 0).mean() < 5
    finally:
        renderer.close()


@pytest.mark.parametrize("bounds", [(0, 0, 0), (-1, 1, 0), (0, 1, -1), (0, float('nan'), 0)])
def test_invalid_clip(bounds):
    with pytest.raises(ValueError):
        Clip("video", *bounds)


def test_legacy_project_opens_with_empty_timeline(tmp_path):
    path = tmp_path / "old.makitop"
    path.write_text('{"format": "makitop", "version": 1, "media": []}')
    assert project_file.load(path).timeline == Timeline()
