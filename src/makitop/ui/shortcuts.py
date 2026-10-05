"""Raccourcis clavier des entrées de menu (Ctrl+S, Ctrl+Maj+S...).

Un raccourci ne fait rien si son entrée de menu n'a pas d'action : les raccourcis
suivent donc automatiquement les fonctionnalités déjà branchées.
"""

from collections.abc import Callable
from dataclasses import dataclass

import dearpygui.dearpygui as dpg

from makitop.ui import menu_bar

HANDLER_TAG = "shortcuts_handler"


@dataclass(frozen=True)
class Shortcut:
    key: int
    letter: str
    ctrl: bool = True
    shift: bool = False

    @property
    def label(self) -> str:
        return "Ctrl+" + ("Maj+" if self.shift else "") + self.letter


SHORTCUTS: dict[str, Shortcut] = {
    menu_bar.NEW_PROJECT: Shortcut(dpg.mvKey_N, "N"),
    menu_bar.OPEN_PROJECT: Shortcut(dpg.mvKey_O, "O"),
    menu_bar.SAVE_PROJECT: Shortcut(dpg.mvKey_S, "S"),
    menu_bar.SAVE_PROJECT_AS: Shortcut(dpg.mvKey_S, "S", shift=True),
    menu_bar.IMPORT_MEDIA: Shortcut(dpg.mvKey_I, "I"),
    menu_bar.QUIT: Shortcut(dpg.mvKey_Q, "Q"),
}


def labels() -> dict[str, str]:
    """Texte affiché à droite de chaque entrée de menu."""
    return {item: shortcut.label for item, shortcut in SHORTCUTS.items()}


def find_action(
    key: int, ctrl: bool, shift: bool, actions: dict[str, Callable[[], None]]
) -> Callable[[], None] | None:
    for item, shortcut in SHORTCUTS.items():
        if (shortcut.key, shortcut.ctrl, shortcut.shift) == (key, ctrl, shift):
            return actions.get(item)
    return None


def install(actions: dict[str, Callable[[], None]]) -> None:
    def on_key(sender, key: int) -> None:
        action = find_action(key, _ctrl_down(), _shift_down(), actions)
        if action is not None:
            action()

    with dpg.handler_registry(tag=HANDLER_TAG):
        dpg.add_key_press_handler(callback=on_key)


def _ctrl_down() -> bool:
    return dpg.is_key_down(dpg.mvKey_LControl) or dpg.is_key_down(dpg.mvKey_RControl)


def _shift_down() -> bool:
    return dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)
