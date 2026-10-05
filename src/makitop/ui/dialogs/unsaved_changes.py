"""Demande « Enregistrer les modifications ? » avant de quitter ou de changer de projet."""

from collections.abc import Callable

import dearpygui.dearpygui as dpg

from makitop.application.projects import ProjectSession

TAG = "unsaved_changes_window"
TEXT_TAG = "unsaved_changes_text"
SAVE_BUTTON = "unsaved_changes_save"
DISCARD_BUTTON = "unsaved_changes_discard"
CANCEL_BUTTON = "unsaved_changes_cancel"
WIDTH = 460

# save(then) enregistre le projet (en demandant un emplacement si besoin) puis appelle then.
SaveThen = Callable[[Callable[[], None]], None]

_session: ProjectSession | None = None
_save: SaveThen | None = None
_pending: Callable[[], None] | None = None


def create(session: ProjectSession, save: SaveThen) -> None:
    global _session, _save
    _session, _save = session, save
    # Pas modale : une fenêtre modale ouverte depuis un menu qui se ferme est aussitôt
    # refermée par Dear PyGui (même problème que pour les erreurs d'import).
    with dpg.window(
        tag=TAG,
        label="Modifications non enregistrées",
        show=False,
        no_collapse=True,
        autosize=True,
        on_close=_cancel,
    ):
        dpg.add_text("", tag=TEXT_TAG, wrap=WIDTH - 20)
        dpg.add_spacer(height=4)
        with dpg.group(horizontal=True):
            dpg.add_button(tag=SAVE_BUTTON, label="Enregistrer", callback=_on_save)
            dpg.add_button(tag=DISCARD_BUTTON, label="Ne pas enregistrer", callback=_on_discard)
            dpg.add_button(tag=CANCEL_BUTTON, label="Annuler", callback=_cancel)


def confirm(then: Callable[[], None]) -> None:
    """Appelle `then` tout de suite si rien n'est à enregistrer ; sinon demande d'abord."""
    global _pending
    if _session is None or not _session.dirty:
        then()
        return
    _pending = then
    dpg.set_value(
        TEXT_TAG,
        f"Enregistrer les modifications de « {_session.project.name} » ?\n"
        "Sinon, elles seront perdues.",
    )
    if dpg.is_viewport_ok():  # pas de viewport dans les tests
        x = max((dpg.get_viewport_client_width() - WIDTH) // 2, 0)
        dpg.set_item_pos(TAG, [x, dpg.get_viewport_client_height() // 3])
    dpg.show_item(TAG)
    dpg.focus_item(TAG)


def _take_pending() -> Callable[[], None] | None:
    global _pending
    dpg.hide_item(TAG)
    pending, _pending = _pending, None
    return pending


def _on_save(*_) -> None:
    pending = _take_pending()
    if pending is not None and _save is not None:
        _save(pending)


def _on_discard(*_) -> None:
    pending = _take_pending()
    if pending is not None:
        pending()


def _cancel(*_) -> None:
    _take_pending()
