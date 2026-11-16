"""Panneau timeline : API publique conservée pour l'assemblage de la fenêtre."""

from makitop.ui.panels.timeline.panel import (
    TAG,
    add_clip,
    bind_clip_moved,
    bind_delete,
    bind_reorder,
    bind_seek,
    bind_zoom,
    clear,
    create,
    set_playhead,
    set_zoom,
    tick,
)

__all__ = [
    "TAG",
    "add_clip",
    "bind",
    "bind_clip_moved",
    "bind_delete",
    "bind_seek",
    "clear",
    "create",
    "refresh",
    "set_playhead",
    "tick",
]

_editor = None


def bind(editor, on_error=None) -> None:
    global _editor
    _editor = editor
    bind_seek(editor.seek)
    bind_delete(lambda clip: _bridge_delete(editor, clip))
    bind_clip_moved(lambda clip: _bridge_moved(editor, clip))
    bind_zoom(editor.set_timeline_zoom)
    bind_reorder(lambda clip, row: editor.reorder_row(clip.id, row))


def refresh() -> None:
    """Réaffiche le montage tel qu'il est dans le projet : clips vidéo et images, une
    ligne par clip dans l'ordre des pistes, avec le zoom enregistré."""
    if _editor is None:
        return
    clear()
    set_zoom(_editor.project.view.timeline_zoom)
    for clip in _editor.rows():
        add_clip(clip)


def _bridge_delete(editor, clip) -> None:
    editor.project.timeline.remove_clip(clip.id)
    if editor.selected_id == clip.id:
        editor.selected_id = None
    editor._edited()


def _bridge_moved(editor, clip) -> None:
    editor._edited()
