"""Barre de menus. Les entrées sont inactives pour l'instant : branchées avec les features."""

import dearpygui.dearpygui as dpg

MENUS: dict[str, list[str]] = {
    "Fichier": [
        "Nouveau projet",
        "Ouvrir...",
        "Enregistrer",
        "Importer un média...",
        "Exporter...",
    ],
    "Édition": ["Annuler", "Rétablir"],
    "Affichage": ["Réinitialiser la disposition"],
    "Aide": ["À propos"],
}


def create() -> None:
    with dpg.menu_bar():
        for menu, items in MENUS.items():
            with dpg.menu(label=menu):
                for item in items:
                    dpg.add_menu_item(label=item, enabled=False)
