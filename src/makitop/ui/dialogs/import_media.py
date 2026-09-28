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
        paths = [Path(p) for p in app_data.get("selections", {}).values()]
        if paths:
            on_files_selected(paths)

    with dpg.file_dialog(
        tag=DIALOG_TAG,
        label="Importer un média",
        show=False,
        modal=True,
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
        modal=True,
        no_resize=True,
        width=ERRORS_WIDTH,
        on_close=_clear_errors,
    ):
        dpg.add_group(tag=ERRORS_LIST_TAG)
        dpg.add_button(label="OK", width=-1, callback=lambda: _close_errors())


def open_dialog() -> None:
    dpg.show_item(DIALOG_TAG)


def show_error(path: Path, message: str) -> None:
    """Ajoute une erreur à la fenêtre d'erreurs et l'affiche (appelable depuis un thread)."""
    dpg.add_text(message, parent=ERRORS_LIST_TAG, wrap=ERRORS_WIDTH - 30)
    if not dpg.is_item_shown(ERRORS_TAG):
        _center(ERRORS_TAG, ERRORS_WIDTH)
        dpg.show_item(ERRORS_TAG)


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
