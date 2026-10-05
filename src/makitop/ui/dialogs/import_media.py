"""Boîte de dialogue « Importer un média » et affichage des erreurs d'import."""

from collections.abc import Callable
from pathlib import Path

import dearpygui.dearpygui as dpg

from makitop.media.probe import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

DIALOG_TAG = "import_media_dialog"
ERRORS_TAG = "import_media_errors"
ERRORS_LIST_TAG = "import_media_errors_list"
ERRORS_WIDTH = 450

_FILTERS: list[tuple[str, frozenset[str]]] = [
    ("Tous les médias", VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS),
    ("Vidéos", VIDEO_EXTENSIONS),
    ("Audio", AUDIO_EXTENSIONS),
    ("Images", IMAGE_EXTENSIONS),
]


def create(on_files_selected: Callable[[list[Path]], None]) -> None:
    """Crée la boîte de dialogue (cachée) ; `open_dialog` l'affiche."""

    def on_ok(sender, app_data) -> None:
        paths = selected_paths(app_data)
        if paths:
            # Les chemins inexistants (nom tapé à la main) sont signalés par l'import.
            on_files_selected(paths)
        else:
            _add_error("Aucun fichier sélectionné.")

    with dpg.file_dialog(
        tag=DIALOG_TAG,
        label="Importer un média",
        show=False,
        modal=True,
        default_filename="",
        file_count=0,  # 0 = sélection multiple sans limite
        width=700,
        height=450,
        callback=on_ok,
    ):
        for label, extensions in _FILTERS:
            dpg.add_file_extension(_filter_string(label, extensions))
        dpg.add_file_extension(".*")

    with dpg.window(
        tag=ERRORS_TAG,
        label="Import impossible",
        show=False,
        # Pas modale : une fenêtre modale ouverte pendant la fermeture du dialogue de fichiers
        # (lui-même modal) est aussitôt refermée par Dear PyGui.
        modal=False,
        no_collapse=True,
        autosize=True,
        width=ERRORS_WIDTH,
        on_close=_clear_errors,
    ):
        dpg.add_group(tag=ERRORS_LIST_TAG)
        dpg.add_button(label="OK", width=-1, callback=lambda: _close_errors())


def open_dialog() -> None:
    dpg.show_item(DIALOG_TAG)


def selected_paths(app_data: dict) -> list[Path]:
    """Fichiers choisis : ceux cliqués dans la liste, sinon le nom tapé dans « File Name »."""
    selections = app_data.get("selections") or {}
    if selections:
        return [Path(p) for p in selections.values()]
    if (app_data.get("file_name") or "").strip():
        return [Path(app_data["file_path_name"])]
    return []


def show_error(path: Path, message: str) -> None:
    """Écouteur `MediaImporter.on_failed` : affiche l'erreur (appelable depuis un thread)."""
    _add_error(message)


def _add_error(message: str) -> None:
    dpg.add_text(message, parent=ERRORS_LIST_TAG, wrap=ERRORS_WIDTH - 30)
    if not dpg.is_item_shown(ERRORS_TAG):
        _center(ERRORS_TAG, ERRORS_WIDTH)
        dpg.show_item(ERRORS_TAG)
    dpg.focus_item(ERRORS_TAG)


def _center(tag: str | int, width: int) -> None:
    if not dpg.is_viewport_ok():  # pas de viewport dans les tests
        return
    x = max((dpg.get_viewport_client_width() - width) // 2, 0)
    dpg.set_item_pos(tag, [x, dpg.get_viewport_client_height() // 3])


def _filter_string(label: str, extensions: frozenset[str]) -> str:
    # Syntaxe Dear PyGui : « Libellé{.ext1,.ext2} ».
    return label + "{" + ",".join(sorted(extensions)) + "}"


def _close_errors() -> None:
    dpg.hide_item(ERRORS_TAG)
    _clear_errors()


def _clear_errors() -> None:
    dpg.delete_item(ERRORS_LIST_TAG, children_only=True)
