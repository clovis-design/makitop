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
            assert dpg.get_item_configuration(export_video.SETTINGS)["show"]
            dpg.set_value(export_video.FPS, "120")
            dpg.set_value(export_video.RESOLUTION, "HD (720p)")
            dialog._choose_file()
            assert dpg.get_item_configuration(export_video.DIALOG)["show"]
            assert dialog.settings.fps == 120
            assert dialog.settings.height == 720
            path = tmp_path / "montage.mp4"
            dialog._chosen(None, {"file_name": path.name, "file_path_name": str(path)})
            project.timeline.clips.clear()
            assert dialog.future.result(timeout=30) == path
            dialog.tick()
            assert dialog.future is None
            assert messages[-1][0] == "Export terminé"
            assert path.is_file()
            assert not dpg.get_item_configuration(export_video.WINDOW)["show"]
    finally:
        dpg.destroy_context()
