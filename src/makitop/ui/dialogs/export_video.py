"""Choix du fichier et suivi d'un export exécuté hors du thread graphique."""

from copy import deepcopy
from threading import Event

import dearpygui.dearpygui as dpg

from makitop.export.mp4 import ExportCancelled, ExportSettings, export_mp4
from makitop.ui.dialogs import message
from makitop.ui.dialogs.file_dialogs import chosen_path

DIALOG = "export_video_dialog"
WINDOW = "export_video_progress"
PROGRESS = "export_video_bar"
CANCEL = "export_video_cancel"
SETTINGS = "export_video_settings"
RESOLUTION = "export_video_resolution"
FPS = "export_video_fps"
QUALITY = "export_video_quality"
RESOLUTIONS = {"HD (720p)": 720, "Full HD (1080p)": 1080, "4K (2160p)": 2160}
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
        with dpg.window(
            tag=SETTINGS, label="Réglages d'export MP4", show=False,
            no_collapse=True, autosize=True,
        ):
            dpg.add_combo(list(RESOLUTIONS), tag=RESOLUTION,
                          label="Résolution", default_value="Full HD (1080p)", width=220)
            dpg.add_combo(["Projet", "24", "25", "30", "48", "50", "60", "90", "120"],
                          tag=FPS, label="Images / seconde", default_value="Projet", width=220)
            dpg.add_combo(list(QUALITIES), tag=QUALITY, label="Qualité",
                          default_value="Haute qualité", width=220)
            dpg.add_text("Le format du cadre est conservé (paysage, portrait ou carré).")
            dpg.add_text("60/120 fps : utilisez des sources à haute cadence pour plus de fluidité.")
            dpg.add_button(label="Choisir le fichier…", callback=self._choose_file)
        with dpg.file_dialog(
            tag=DIALOG, label="Exporter en MP4", show=False, modal=True,
            width=700, height=450, file_count=1, callback=self._chosen,
        ):
            dpg.add_file_extension("Vidéo MP4{.mp4}")
        with dpg.window(
            tag=WINDOW, label="Export MP4", show=False, no_close=True,
            no_collapse=True, autosize=True,
        ):
            dpg.add_text("Encodage du montage en H.264 / AAC…")
            dpg.add_progress_bar(tag=PROGRESS, width=400)
            dpg.add_button(tag=CANCEL, label="Annuler", callback=self._cancel)

    def open(self):
        if self.future is not None:
            dpg.show_item(WINDOW)
            return
        if not self.session.project.timeline.clips:
            message.show("Export impossible", "Ajoutez un média à la timeline avant d'exporter.")
            return
        dpg.show_item(SETTINGS)

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
        dpg.show_item(DIALOG)

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
        dpg.show_item(WINDOW)

    def _progress(self, value):
        self.progress = value

    def _cancel(self):
        self.cancel.set()
        dpg.configure_item(CANCEL, enabled=False)

    def tick(self):
        if self.future is None:
            return
        dpg.set_value(PROGRESS, self.progress)
        dpg.configure_item(PROGRESS, overlay=f"{self.progress:.0%}")
        if not self.future.done():
            return
        future, self.future = self.future, None
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
