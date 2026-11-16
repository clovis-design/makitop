import dearpygui.dearpygui as dpg
import numpy as np
import pytest

from makitop.engine.timeline import TimelineRenderer
from makitop.model.project import Project
from makitop.ui.panels import preview


def test_preview_texture_retains_native_size_and_reuses_buffer():
    dpg.create_context()
    try:
        preview.create_video_texture()
        with dpg.window():
            preview.create()
        for height, width in [(720, 1280), (1920, 1080), (1080, 1080)]:
            frame = np.full((height, width, 3), 127, dtype=np.uint8)
            previous_texture = preview._texture
            preview.update_frame(frame)
            assert not dpg.does_item_exist(previous_texture)
            config = dpg.get_item_configuration(preview._texture)
            assert (config["width"], config["height"]) == (width, height)
            pixels = preview._pixels
            assert pixels.dtype == np.float32
            np.testing.assert_allclose(pixels[:, :, :3], 127 / 255)
            assert np.all(pixels[:, :, 3] == 1)
            preview.update_frame(frame)
            assert preview._pixels is pixels
    finally:
        dpg.destroy_context()


@pytest.mark.parametrize("format,size", [("16:9", (720, 1280)), ("9:16", (1280, 720)),
                                        ("1:1", (720, 720))])
def test_preview_resolution_and_aspect_ratio(format, size):
    renderer = TimelineRenderer()
    try:
        project = Project(canvas_format=format)
        assert renderer.render(project, 0).shape[:2] == size
        renderer.set_preview_height(1080)
        assert renderer.render(project, 0).shape[:2] == tuple(n * 3 // 2 for n in size)
    finally:
        renderer.close()
