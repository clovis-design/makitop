from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

from makitop.engine.timeline import TimelineRenderer
from makitop.media.probe import probe
from makitop.model.composition import Transform
from makitop.model.project import Project
from makitop.model.timeline import ImageClip, MediaClip, Timeline


def photo(tmp_path, name, color, size=(64, 48)):
    path = tmp_path / name
    Image.new("RGBA", size, color).save(path)
    return probe(path)


def test_photo_and_video_side_by_side(video_file, tmp_path):
    image = photo(tmp_path, "red.png", (255, 0, 0, 255))
    video = probe(video_file)
    project = Project(timeline=Timeline(clips=[
        ImageClip(0, image, 1, transform=Transform(width=0.5)),
        MediaClip(0, video, 0, 1, track=1, transform=Transform(x=0.5, width=0.5)),
    ]))
    renderer = TimelineRenderer(128, 48)
    try:
        frame = renderer.render(project, 9)
        np.testing.assert_array_equal(frame[24, 32], [255, 0, 0])
        assert frame[:, 64:].mean() == pytest.approx(60, abs=5)
    finally:
        renderer.close()


def test_two_instances_of_video_play_different_source_portions(video_file):
    video = probe(video_file)
    project = Project(timeline=Timeline(clips=[
        MediaClip(0, video, 0.1, 0.4, transform=Transform(width=0.5)),
        MediaClip(0, video, 0.6, 0.9, track=1, transform=Transform(x=0.5, width=0.5)),
    ]))
    renderer = TimelineRenderer(128, 48)
    try:
        frame = renderer.render(project, 0)
        assert frame[:, :64].mean() == pytest.approx(20, abs=5)
        assert frame[:, 64:].mean() == pytest.approx(120, abs=5)
        assert not renderer.render(project, 10).any()
    finally:
        renderer.close()


def test_layer_order_transparency_and_cache_invalidation(tmp_path):
    red = photo(tmp_path, "red.png", (255, 0, 0, 255))
    blue = photo(tmp_path, "blue.png", (0, 0, 255, 128))
    foreground = ImageClip(0, blue, 2, track=2)
    background = ImageClip(0, red, 2, track=0)
    project = Project(timeline=Timeline(clips=[foreground, background]))
    renderer = TimelineRenderer(64, 48)
    try:
        frame = renderer.render(project, 0)
        np.testing.assert_array_equal(frame[0, 0], [127, 0, 128])
        assert renderer.render(project, 0) is frame
        foreground.track = 0
        background.track = 2
        np.testing.assert_array_equal(renderer.render(project, 0)[0, 0], [255, 0, 0])
        background.transform = Transform(x=2)
        np.testing.assert_array_equal(renderer.render(project, 0)[0, 0], [0, 0, 128])
    finally:
        renderer.close()


def test_crop_and_off_canvas_clipping(tmp_path):
    path = tmp_path / "split.png"
    pixels = np.zeros((100, 100, 3), dtype=np.uint8)
    pixels[:, :50] = (255, 0, 0)
    pixels[:, 50:] = (0, 255, 0)
    Image.fromarray(pixels).save(path)
    clip = ImageClip(0, probe(path), 1,
                     transform=Transform(width=0.5, crop_left=0.5))
    project = Project(timeline=Timeline(clips=[clip]))
    renderer = TimelineRenderer(100, 100)
    try:
        frame = renderer.render(project, 0)
        assert (frame[:, :50, 1] == 255).all()
        assert not frame[:, 50:].any()
        clip.transform = replace(clip.transform, x=-0.25)
        frame = renderer.render(project, 0)
        assert (frame[:, :25, 1] == 255).all()
        assert not frame[:, 25:].any()
    finally:
        renderer.close()


def test_photo_orientation_matches_selection_geometry(tmp_path):
    path = tmp_path / "portrait.jpg"
    image = Image.new("RGB", (80, 40), (255, 0, 0))
    exif = image.getexif()
    exif[274] = 6  # rotation horaire de 90 degrés
    image.save(path, exif=exif)
    media = probe(path)
    assert (media.width, media.height) == (40, 80)
    renderer = TimelineRenderer(40, 80)
    try:
        frame = renderer.render(Project(timeline=Timeline(clips=[ImageClip(0, media, 1)])), 0)
        assert frame[:, :, 0].min() > 250
    finally:
        renderer.close()


@pytest.mark.parametrize("canvas_format,ratio", [("16:9", 16 / 9), ("9:16", 9 / 16), ("1:1", 1)])
def test_preview_format(canvas_format, ratio):
    renderer = TimelineRenderer()
    try:
        frame = renderer.render(Project(canvas_format=canvas_format), 0)
        assert frame.shape[1] / frame.shape[0] == pytest.approx(ratio, abs=0.003)
    finally:
        renderer.close()
