"""Actions du menu Fichier sur les projets : nouveau, ouvrir, enregistrer, enregistrer sous,
quitter.

Avant d'abandonner des modifications (nouveau, ouvrir, quitter), l'utilisateur doit
confirmer (ui/dialogs/unsaved_changes.py). Les erreurs (fichier introuvable, corrompu,
disque plein...) sont affichées dans une fenêtre de message.
"""

from collections.abc import Callable
from pathlib import Path

import dearpygui.dearpygui as dpg

from makitop.application.projects import ProjectSession
from makitop.storage.project_file import EXTENSION, ProjectFileError
from makitop.ui.dialogs import message, missing_media, unsaved_changes
from makitop.ui.dialogs.file_dialogs import chosen_path

OPEN_DIALOG_TAG = "open_project_dialog"
SAVE_DIALOG_TAG = "save_project_dialog"

_FILTER = f"Projets Makitop{{{EXTENSION}}}"
_session: ProjectSession | None = None
# Action à reprendre après « Enregistrer sous » (ex. quitter après avoir enregistré).
_after_save: Callable[[], None] | None = None

__all__ = ["chosen_path"]  # réexporté pour les appelants existants


def create(session: ProjectSession) -> None:
    """Crée les dialogues (cachés). À appeler une fois, après la fenêtre principale."""
    global _session
    _session = session
    message.create()
    unsaved_changes.create(session, save=save)
    missing_media.create(session)

    with dpg.file_dialog(
        tag=OPEN_DIALOG_TAG,
        label="Ouvrir un projet",
        show=False,
        modal=True,
        default_filename="",
        file_count=1,
        width=700,
        height=450,
        callback=lambda _, app_data: _on_path_chosen(app_data, open_path),
    ):
        dpg.add_file_extension(_FILTER)

    with dpg.file_dialog(
        tag=SAVE_DIALOG_TAG,
        label="Enregistrer le projet",
        show=False,
        modal=True,
        default_filename="",
        file_count=1,
        width=700,
        height=450,
        callback=lambda _, app_data: _on_path_chosen(app_data, save_as),
        cancel_callback=_on_save_cancelled,
    ):
        dpg.add_file_extension(_FILTER)


def new_project() -> None:
    unsaved_changes.confirm(_require_session().new)


def open_dialog() -> None:
    unsaved_changes.confirm(lambda: dpg.show_item(OPEN_DIALOG_TAG))


def open_recent(path: Path) -> None:
    unsaved_changes.confirm(lambda: open_path(path))


def open_path(path: Path) -> None:
    """Ouvre sans confirmation (déjà demandée, ou lancement de l'application)."""
    try:
        _require_session().open(path)
    except ProjectFileError as error:
        message.show("Ouverture impossible", str(error))
        return
    missing_media.show_if_missing()


def quit_app() -> None:
    unsaved_changes.confirm(dpg.stop_dearpygui)


def save(then: Callable[[], None] | None = None) -> None:
    """Enregistre, puis appelle `then` si l'enregistrement a réussi. Demande un
    emplacement si le projet n'a jamais été enregistré."""
    session = _require_session()
    if session.path is None:
        save_dialog(then)
        return
    if _save(session.save) and then is not None:
        then()


def save_dialog(then: Callable[[], None] | None = None) -> None:
    global _after_save
    _after_save = then
    session = _require_session()
    dpg.configure_item(SAVE_DIALOG_TAG, default_filename=session.project.name)
    if session.path is not None:
        dpg.configure_item(SAVE_DIALOG_TAG, default_path=str(session.path.parent))
    dpg.show_item(SAVE_DIALOG_TAG)


def save_as(path: Path) -> None:
    then = _take_after_save()
    if _save(lambda: _require_session().save_as(path)) and then is not None:
        then()


def _on_save_cancelled(*_) -> None:
    _take_after_save()


def _take_after_save() -> Callable[[], None] | None:
    global _after_save
    then, _after_save = _after_save, None
    return then


def _on_path_chosen(app_data: dict, action) -> None:
    path = chosen_path(app_data)
    if path is not None:
        action(path)
    else:
        _take_after_save()


def _save(do_save: Callable[[], None]) -> bool:
    try:
        do_save()
    except ProjectFileError as error:
        message.show("Enregistrement impossible", str(error))
        return False
    return True


def _require_session() -> ProjectSession:
    if _session is None:
        raise RuntimeError("project_file.create() doit être appelé avant les actions.")
    return _session
