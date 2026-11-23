from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import dearpygui.dearpygui as dpg

from makitop.media.probe import probe
from makitop.model.project import Project
from makitop.model.timeline import ImageClip, Timeline
from makitop.ui.dialogs import export_video


def test_dialog_exports_snapshot_and_reports_success(tmp_path, image_file, monkeypatch):
    project = Project(timeline=Timeline(clips=[ImageClip(0, probe(image_file), 0.1)]))
    session = SimpleNamespace(project=project, path=None)
    messages = []
    monkeypatch.setattr(export_video.message, "show", lambda *args: messages.append(args))
    dpg.create_context()
    try:
        with ThreadPoolExecutor() as executor:
            dialog = export_video.ExportDialog(session, executor)
            dialog.open()
            assert dialog.blocks_editor()
            assert dpg.get_item_configuration(export_video.SETTINGS)["modal"]
            assert dpg.get_item_configuration(export_video.WINDOW)["modal"]
            dialog.tick()
            dialog.tick()
            assert dpg.get_item_configuration(export_video.SETTINGS)["show"]
            dpg.set_value(export_video.FPS, "120")
            dpg.set_value(export_video.RESOLUTION, "HD (720p)")
            dialog._choose_file()
            assert dialog.blocks_editor()
            dialog.tick()
            dialog.tick()
            assert dpg.get_item_configuration(export_video.DIALOG)["show"]
            assert dialog.settings.fps == 120
            assert dialog.settings.height == 720
            path = tmp_path / "montage.mp4"
            dialog._chosen(None, {"file_name": path.name, "file_path_name": str(path)})
            assert dialog.blocks_editor()
            project.timeline.clips.clear()
            assert dialog.future.result(timeout=30) == path
            dialog.tick()
            assert dialog.future is None
            assert messages[-1][0] == "Export terminé"
            assert path.is_file()
            assert not dpg.get_item_configuration(export_video.WINDOW)["show"]
            assert not dialog.blocks_editor()
    finally:
        dpg.destroy_context()


def test_export_defaults_match_player_and_project(image_file):
    project = Project(
        canvas_format="9:16",
        timeline=Timeline(fps=50, clips=[ImageClip(0, probe(image_file), 0.1)]),
    )
    session = SimpleNamespace(project=project, path=None)
    dpg.create_context()
    try:
        with dpg.window():
            dpg.add_combo(["Fluide (360p)", "HD (720p)", "Full HD (1080p)"],
                          tag="preview_quality", default_value="HD (720p)")
        dialog = export_video.ExportDialog(session, None)
        dialog.open()
        assert dpg.get_value(export_video.RESOLUTION) == "HD (720p)"
        assert dpg.get_value(export_video.FPS) == "50"
        assert dpg.get_value(export_video.SUMMARY) == "9:16  ·  720 × 1280  ·  50 fps"
        dialog._choose_file()
        assert dialog.settings.height == 720
        assert dialog.settings.fps == 50
        dpg.set_value("preview_quality", "Fluide (360p)")
        project.timeline.fps = 24
        dialog.open()
        assert dpg.get_value(export_video.RESOLUTION) == "Fluide (360p)"
        assert dpg.get_value(export_video.FPS) == "24"
        assert dpg.get_value(export_video.SUMMARY) == "9:16  ·  360 × 640  ·  24 fps"
        dpg.set_value(export_video.RESOLUTION, "4K (2160p)")
        dpg.get_item_callback(export_video.RESOLUTION)(None, "4K (2160p)")
        assert dpg.get_value(export_video.SUMMARY) == "9:16  ·  2160 × 3840  ·  24 fps"
    finally:
        dpg.destroy_context()


def test_export_defaults_support_custom_project_fps(image_file):
    project = Project(timeline=Timeline(fps=37, clips=[ImageClip(0, probe(image_file), 0.1)]))
    dpg.create_context()
    try:
        dialog = export_video.ExportDialog(SimpleNamespace(project=project, path=None), None)
        dialog.open()
        assert dpg.get_value(export_video.FPS) == "37"
        assert "37" in dpg.get_item_configuration(export_video.FPS)["items"]
        assert dpg.get_value(export_video.RESOLUTION) == "HD (720p)"
        dialog._choose_file()
        assert dialog.settings.fps == 37
    finally:
        dpg.destroy_context()
