"""Fenêtre « Médias introuvables » : liste les médias déplacés ou supprimés et permet
de les relier à leur nouvel emplacement."""

from pathlib import Path

import dearpygui.dearpygui as dpg

from makitop.application.projects import ProjectSession
from makitop.media.probe import MediaProbeError
from makitop.model.media import Media
from makitop.ui.dialogs import message
from makitop.ui.dialogs.file_dialogs import chosen_path

TAG = "missing_media_window"
LIST_TAG = "missing_media_list"
FILE_DIALOG_TAG = "missing_media_file_dialog"
WIDTH = 560

_session: ProjectSession | None = None
_target: Media | None = None


def create(session: ProjectSession) -> None:
    global _session
    _session = session
    with dpg.window(
        tag=TAG,
        label="Médias introuvables",
        show=False,
        no_collapse=True,
        autosize=True,
    ):
        dpg.add_text(
            "Ces fichiers ont été déplacés ou supprimés. Indique leur nouvel emplacement : "
            "les autres médias manquants du même dossier seront retrouvés automatiquement.",
            wrap=WIDTH - 20,
        )
        dpg.add_separator()
        dpg.add_group(tag=LIST_TAG)
        dpg.add_separator()
        dpg.add_button(label="Fermer", width=WIDTH - 16, callback=lambda: dpg.hide_item(TAG))

    with dpg.file_dialog(
        tag=FILE_DIALOG_TAG,
        label="Rechercher le média",
        show=False,
        modal=True,
        default_filename="",
        file_count=1,
        width=700,
        height=450,
        callback=_on_file_chosen,
        cancel_callback=_forget_target,
    ):
        dpg.add_file_extension(".*")


def show_if_missing() -> None:
    """Affiche la fenêtre seulement s'il manque des médias (appelé après une ouverture)."""
    if _require_session().project.missing_media():
        show()


def show() -> None:
    _refresh()
    if dpg.is_viewport_ok():  # pas de viewport dans les tests
        x = max((dpg.get_viewport_client_width() - WIDTH) // 2, 0)
        dpg.set_item_pos(TAG, [x, dpg.get_viewport_client_height() // 4])
    dpg.show_item(TAG)
    dpg.focus_item(TAG)


def relink(media: Media, path: Path) -> None:
    try:
        relinked = _require_session().relink(media, path)
    except MediaProbeError as error:
        message.show("Impossible de relier le média", str(error))
        return
    _refresh()
    if not _require_session().project.missing_media():
        dpg.hide_item(TAG)
        found = len(relinked)
        message.show(
            "Médias retrouvés",
            "Tous les médias ont été retrouvés."
            if found == 1
            else f"{found} médias retrouvés : tous les médias sont de nouveau disponibles.",
        )


def _refresh() -> None:
    dpg.delete_item(LIST_TAG, children_only=True)
    missing = _require_session().project.missing_media()
    if not missing:
        dpg.add_text("Aucun média introuvable.", parent=LIST_TAG)
        return
    for media in missing:
        with dpg.group(horizontal=True, parent=LIST_TAG):
            dpg.add_button(
                label="Rechercher...",
                callback=lambda *_, m=media: _choose_file_for(m),
            )
            with dpg.group():
                dpg.add_text(f"{media.name}{media.extension}")
                dpg.add_text(str(media.path), color=(150, 150, 150), wrap=WIDTH - 130)


def _choose_file_for(media: Media) -> None:
    global _target
    _target = media
    dpg.configure_item(FILE_DIALOG_TAG, default_filename=media.path.name)
    dpg.show_item(FILE_DIALOG_TAG)


def _on_file_chosen(sender, app_data: dict) -> None:
    media, path = _forget_target(), chosen_path(app_data)
    if media is not None and path is not None:
        relink(media, path)


def _forget_target(*_) -> Media | None:
    global _target
    media, _target = _target, None
    return media


def _require_session() -> ProjectSession:
    if _session is None:
        raise RuntimeError("missing_media.create() doit être appelé avant show().")
    return _session
