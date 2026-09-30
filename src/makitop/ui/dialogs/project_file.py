"""Actions du menu Fichier sur les projets : nouveau, ouvrir, enregistrer, enregistrer sous.

Les erreurs (fichier introuvable, corrompu, disque plein...) sont affichées dans une
fenêtre de message au lieu d'interrompre l'application.
"""

from pathlib import Path

import dearpygui.dearpygui as dpg

from makitop.application.projects import ProjectSession
from makitop.storage.project_file import EXTENSION, ProjectFileError
from makitop.ui.dialogs import message

OPEN_DIALOG_TAG = "open_project_dialog"
SAVE_DIALOG_TAG = "save_project_dialog"

_FILTER = f"Projets Makitop{{{EXTENSION}}}"
_session: ProjectSession | None = None


def create(session: ProjectSession) -> None:
    """Crée les dialogues (cachés). À appeler une fois, après la fenêtre principale."""
    global _session
    _session = session
    message.create()

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
    ):
        dpg.add_file_extension(_FILTER)


def new_project() -> None:
    _require_session().new()


def open_dialog() -> None:
    dpg.show_item(OPEN_DIALOG_TAG)


def open_path(path: Path) -> None:
    try:
        _require_session().open(path)
    except ProjectFileError as error:
        message.show("Ouverture impossible", str(error))


def save() -> None:
    """Enregistre ; demande un emplacement si le projet n'a jamais été enregistré."""
    session = _require_session()
    if session.path is None:
        save_dialog()
        return
    _save(lambda: session.save())


def save_dialog() -> None:
    session = _require_session()
    dpg.configure_item(SAVE_DIALOG_TAG, default_filename=session.project.name)
    if session.path is not None:
        dpg.configure_item(SAVE_DIALOG_TAG, default_path=str(session.path.parent))
    dpg.show_item(SAVE_DIALOG_TAG)


def save_as(path: Path) -> None:
    _save(lambda: _require_session().save_as(path))


def chosen_path(app_data: dict) -> Path | None:
    """Fichier choisi dans un dialogue : celui cliqué, sinon le nom tapé."""
    selections = app_data.get("selections") or {}
    if selections:
        return Path(next(iter(selections.values())))
    if (app_data.get("file_name") or "").strip():
        return Path(app_data["file_path_name"])
    return None


def _on_path_chosen(app_data: dict, action) -> None:
    path = chosen_path(app_data)
    if path is not None:
        action(path)


def _save(do_save) -> None:
    try:
        do_save()
    except ProjectFileError as error:
        message.show("Enregistrement impossible", str(error))


def _require_session() -> ProjectSession:
    if _session is None:
        raise RuntimeError("project_file.create() doit être appelé avant les actions.")
    return _session
