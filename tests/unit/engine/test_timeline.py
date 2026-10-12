import av
import numpy as np
import pytest

from makitop.engine.cache import FrameCache
from makitop.engine.timeline import TimelineRenderer
from makitop.media.probe import probe
from makitop.model.project import Project
from makitop.model.timeline import MediaClip, Timeline
from makitop.storage import project_file


def test_hold_source_frame_until_next_timestamp(video_file):
    media = probe(video_file)
    clip = MediaClip(timeline_start=0.0, media=media, source_start=0.0, source_end=0.9)
    project = Project(media=[media], timeline=Timeline(clips=[clip]))
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
    clip = MediaClip(timeline_start=0.2, media=media, source_start=0.5, source_end=0.9)
    project = Project(media=[media], timeline=Timeline(clips=[clip]))
    renderer = TimelineRenderer(64, 48)
    try:
        assert not renderer.render(project, 0).any()
        old = renderer.render(project, 6)
        assert renderer.render(project, 6) is old
        clip2 = MediaClip(timeline_start=0.2, media=media, source_start=0.1, source_end=0.5)
        project.timeline = Timeline(clips=[clip2])
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
    clip_a = MediaClip(timeline_start=0.0, media=a, source_start=0.0, source_end=0.3)
    clip_b = MediaClip(timeline_start=0.3, media=b, source_start=0.2, source_end=0.5)
    project = Project(media=[a, b], timeline=Timeline(clips=[clip_a, clip_b]))
    renderer = TimelineRenderer(64, 48)
    try:
        assert renderer.render(project, 8).mean() < 50
        assert renderer.render(project, 9).mean() > 210
        assert renderer.render(project, 0).mean() < 5
    finally:
        renderer.close()


def test_legacy_project_opens_with_empty_timeline(tmp_path):
    path = tmp_path / "old.makitop"
    path.write_text('{"format": "makitop", "version": 1, "media": []}')
    assert project_file.load(path).timeline == Timeline()
