"""Barre de menus. Une entrée est active dès qu'une action lui est associée."""

from collections.abc import Callable

import dearpygui.dearpygui as dpg

IMPORT_MEDIA = "Importer un média..."

MENUS: dict[str, list[str]] = {
    "Fichier": [
        "Nouveau projet",
        "Ouvrir...",
        "Enregistrer",
        IMPORT_MEDIA,
        "Exporter...",
    ],
    "Édition": ["Annuler", "Rétablir"],
    "Affichage": ["Réinitialiser la disposition"],
    "Aide": ["À propos"],
}


def item_tag(label: str) -> str:
    return f"menu_item_{label}"


def create(actions: dict[str, Callable[[], None]] | None = None) -> None:
    actions = actions or {}
    with dpg.menu_bar():
        for menu, items in MENUS.items():
            with dpg.menu(label=menu):
                for item in items:
                    action = actions.get(item)
                    dpg.add_menu_item(
                        tag=item_tag(item),
                        label=item,
                        enabled=action is not None,
                        callback=_run(action) if action else None,
                    )


def _run(action: Callable[[], None]) -> Callable:
    # Dear PyGui passe (sender, app_data, user_data) ; les actions n'en ont pas besoin.
    return lambda *_: action()
