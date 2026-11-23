"""Choix du fichier et suivi d'un export exécuté hors du thread graphique."""

from copy import deepcopy
from threading import Event

import dearpygui.dearpygui as dpg

from makitop.export.mp4 import ExportCancelled, ExportSettings, export_mp4
from makitop.model.composition import FORMATS
from makitop.ui.dialogs import message
from makitop.ui.dialogs.file_dialogs import chosen_path
from makitop.ui.panels.preview import FPS_CHOICES, PREVIEW_QUALITIES

DIALOG = "export_video_dialog"
WINDOW = "export_video_progress"
PROGRESS = "export_video_bar"
CANCEL = "export_video_cancel"
SETTINGS = "export_video_settings"
RESOLUTION = "export_video_resolution"
FPS = "export_video_fps"
QUALITY = "export_video_quality"
SUMMARY = "export_video_summary"
FPS_NOTE = "export_video_fps_note"
RESOLUTIONS = {**PREVIEW_QUALITIES, "4K (2160p)": 2160}
QUALITIES = {
    "Haute qualité": (18, "medium"),
    "Qualité maximale (plus lent)": (16, "slow"),
    "Rapide": (20, "fast"),
}


class ExportDialog:
    def __init__(self, session, executor):
        self.session = session
        self.executor = executor
        self.future = None
        self.cancel = Event()
        self.progress = 0.0
        self.settings = ExportSettings()
        self._pending_window = None
        self._pending_frames = 0
        with dpg.window(
            tag=SETTINGS, label="Réglages d'export MP4", show=False,
            no_collapse=True, autosize=True, modal=True,
        ):
            dpg.add_text("Montage à exporter")
            dpg.add_text("", tag=SUMMARY)
            dpg.add_separator()
            dpg.add_text("Réglages de sortie")
            dpg.add_combo(list(RESOLUTIONS), tag=RESOLUTION,
                          label="Résolution", default_value="HD (720p)", width=220,
                          callback=self._update_summary)
            dpg.add_combo(["Projet", *FPS_CHOICES],
                          tag=FPS, label="Images / seconde", default_value="60", width=220,
                          callback=self._update_summary)
            dpg.add_combo(list(QUALITIES), tag=QUALITY, label="Qualité",
                          default_value="Haute qualité", width=220)
            dpg.add_text("Cadence élevée : privilégiez des sources à haute cadence.",
                         tag=FPS_NOTE, show=False)
            dpg.add_spacer(height=4)
            dpg.add_button(label="Choisir le fichier…", callback=self._choose_file)
        with dpg.file_dialog(
            tag=DIALOG, label="Exporter en MP4", show=False, modal=True,
            width=700, height=450, file_count=1, callback=self._chosen,
        ):
            dpg.add_file_extension("Vidéo MP4{.mp4}")
        with dpg.window(
            tag=WINDOW, label="Export MP4", show=False, no_close=True,
            no_collapse=True, autosize=True, modal=True,
        ):
            dpg.add_text("Encodage du montage en H.264 / AAC…")
            dpg.add_progress_bar(tag=PROGRESS, width=400)
            dpg.add_button(tag=CANCEL, label="Annuler", callback=self._cancel)

    def open(self):
        if self.future is not None:
            self._show_after_popup(WINDOW)
            return
        if not self.session.project.timeline.clips:
            message.show("Export impossible", "Ajoutez un média à la timeline avant d'exporter.")
            return
        project = self.session.project
        preview_height = (PREVIEW_QUALITIES.get(dpg.get_value("preview_quality"))
                          if dpg.does_item_exist("preview_quality") else None)
        height = preview_height or 720
        dpg.set_value(RESOLUTION, next(label for label, size in RESOLUTIONS.items()
                                       if size == height))
        fps = str(project.timeline.fps)
        choices = ["Projet", *FPS_CHOICES]
        if fps not in choices:
            choices.append(fps)
        dpg.configure_item(FPS, items=choices)
        dpg.set_value(FPS, fps)
        self._update_summary()
        self._show_after_popup(SETTINGS)

    def _show_after_popup(self, tag):
        # Ouvrir une modale pendant la fermeture du menu ou du dialogue de fichiers
        # la referme aussitôt dans Dear PyGui. L'afficher à l'image suivante.
        self._pending_window = tag
        self._pending_frames = 1

    def blocks_editor(self):
        return self._pending_window is not None or any(
            dpg.is_item_shown(tag) for tag in (SETTINGS, DIALOG, WINDOW)
        )

    def _update_summary(self, sender=None, app_data=None):
        project = self.session.project
        base_w, base_h = FORMATS[project.canvas_format]
        height = RESOLUTIONS[dpg.get_value(RESOLUTION)]
        width, height_px = base_w * height // 1080, base_h * height // 1080
        fps = dpg.get_value(FPS)
        fps = project.timeline.fps if fps == "Projet" else int(fps)
        dpg.set_value(SUMMARY, f"{project.canvas_format}  ·  {width} × {height_px}  ·  {fps} fps")
        dpg.configure_item(FPS_NOTE, show=fps > 60)

    def _choose_file(self):
        fps = dpg.get_value(FPS)
        crf, preset = QUALITIES[dpg.get_value(QUALITY)]
        self.settings = ExportSettings(
            height=RESOLUTIONS[dpg.get_value(RESOLUTION)],
            fps=None if fps == "Projet" else int(fps), crf=crf, preset=preset,
        )
        dpg.hide_item(SETTINGS)
        dpg.configure_item(DIALOG, default_filename=self.session.project.name + ".mp4")
        if self.session.path is not None:
            dpg.configure_item(DIALOG, default_path=str(self.session.path.parent))
        self._show_after_popup(DIALOG)

    def _chosen(self, sender, app_data):
        path = chosen_path(app_data)
        if path is None or self.future is not None:
            return
        project = deepcopy(self.session.project)
        self.cancel.clear()
        self.progress = 0.0
        dpg.set_value(PROGRESS, 0.0)
        dpg.configure_item(CANCEL, enabled=True)
        self.future = self.executor.submit(
            export_mp4, project, path, settings=self.settings,
            progress=self._progress, cancel=self.cancel,
        )
        dpg.hide_item(DIALOG)
        self._show_after_popup(WINDOW)

    def _progress(self, value):
        self.progress = value

    def _cancel(self):
        self.cancel.set()
        dpg.configure_item(CANCEL, enabled=False)

    def tick(self):
        if self._pending_window is not None:
            if self._pending_frames:
                self._pending_frames -= 1
            else:
                dpg.show_item(self._pending_window)
                dpg.focus_item(self._pending_window)
                self._pending_window = None
        if self.future is None:
            return
        dpg.set_value(PROGRESS, self.progress)
        dpg.configure_item(PROGRESS, overlay=f"{self.progress:.0%}")
        if not self.future.done():
            return
        future, self.future = self.future, None
        self._pending_window = None
        dpg.hide_item(WINDOW)
        try:
            path = future.result()
        except ExportCancelled:
            message.show("Export annulé", "L'export a été annulé.")
        except Exception as exc:
            message.show("Export impossible", str(exc))
        else:
            message.show("Export terminé", f"Vidéo enregistrée :\n{path}")

    def close(self):
        self.cancel.set()
