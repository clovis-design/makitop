"""Barre de menus. Une entrée est active dès qu'une action lui est associée."""

from collections.abc import Callable
from pathlib import Path

import dearpygui.dearpygui as dpg

NEW_PROJECT = "Nouveau projet"
OPEN_PROJECT = "Ouvrir..."
RECENT_PROJECTS = "Projets récents"
SAVE_PROJECT = "Enregistrer"
SAVE_PROJECT_AS = "Enregistrer sous..."
IMPORT_MEDIA = "Importer un média..."

RECENT_MENU_TAG = "menu_recent_projects"

MENUS: dict[str, list[str]] = {
    "Fichier": [
        NEW_PROJECT,
        OPEN_PROJECT,
        RECENT_PROJECTS,
        SAVE_PROJECT,
        SAVE_PROJECT_AS,
        IMPORT_MEDIA,
        "Exporter...",
    ],
    "Édition": ["Annuler", "Rétablir"],
    "Affichage": ["Réinitialiser la disposition"],
    "Aide": ["À propos"],
}


def item_tag(label: str) -> str:
    return f"menu_item_{label}"


def create(
    actions: dict[str, Callable[[], None]] | None = None,
    shortcuts: dict[str, str] | None = None,
) -> None:
    """`shortcuts` associe un libellé d'entrée au raccourci affiché (ex. « Ctrl+S »)."""
    actions = actions or {}
    shortcuts = shortcuts or {}
    with dpg.menu_bar():
        for menu, items in MENUS.items():
            with dpg.menu(label=menu):
                for item in items:
                    if item == RECENT_PROJECTS:
                        # Sous-menu rempli par set_recent_projects.
                        with dpg.menu(label=item, tag=RECENT_MENU_TAG):
                            _add_empty_recent()
                        continue
                    action = actions.get(item)
                    dpg.add_menu_item(
                        tag=item_tag(item),
                        label=item,
                        shortcut=shortcuts.get(item, ""),
                        enabled=action is not None,
                        callback=_run(action) if action else None,
                    )


def set_recent_projects(paths: list[Path], on_select: Callable[[Path], None]) -> None:
    """Remplace le contenu du sous-menu « Projets récents »."""
    dpg.delete_item(RECENT_MENU_TAG, children_only=True)
    if not paths:
        _add_empty_recent()
        return
    for path in paths:
        dpg.add_menu_item(
            label=f"{path.stem}   ({path.parent})",
            parent=RECENT_MENU_TAG,
            callback=lambda *_, p=path: on_select(p),
        )


def _add_empty_recent() -> None:
    dpg.add_menu_item(label="(aucun)", parent=RECENT_MENU_TAG, enabled=False)


def _run(action: Callable[[], None]) -> Callable:
    # Dear PyGui passe (sender, app_data, user_data) ; les actions n'en ont pas besoin.
    return lambda *_: action()
