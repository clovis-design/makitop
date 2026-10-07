import dearpygui.dearpygui as dpg

from makitop.media.probe import probe
from makitop.model.project import Project
from makitop.ui import main_window
from makitop.ui.panels import timeline


def test_timeline_controls_and_selection(video_file):
    dpg.create_context()
    try:
        main_window.build()
        calls = []
        timeline.bind(
            lambda start, end: calls.append((start, end)),
            lambda: calls.append("show"),
            lambda position: calls.append(position),
            lambda: calls.append("split"),
            lambda: calls.append("remove"),
        )
        media = probe(video_file)
        project = Project(media=[media])
        project.timeline.append(media.id, 0.1, 0.8)
        timeline.select_media(media)
        timeline.refresh(project)
        assert timeline.selected_index() == 0
        assert dpg.get_item_configuration("timeline_cursor")["max_value"] > 0.69
        dpg.set_value("timeline_source_in", 0.2)
        dpg.set_value("timeline_source_out", 0.7)
        dpg.get_item_callback("timeline_add")()
        dpg.get_item_callback("timeline_show")()
        dpg.get_item_callback("timeline_cursor")(None, 0.5)
        dpg.get_item_callback("timeline_split")()
        dpg.get_item_callback("timeline_remove")()
        assert calls[0][0] > 0.19
        assert calls[1:] == ["show", 0.5, "split", "remove"]
    finally:
        dpg.destroy_context()
