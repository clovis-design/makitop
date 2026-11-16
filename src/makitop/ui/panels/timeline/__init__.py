"""Panneau timeline : API publique conservée pour l'assemblage de la fenêtre."""

from makitop.model.timeline import MediaClip
from makitop.ui.panels.timeline.panel import TAG, add_clip, bind_clip_moved, bind_delete, bind_seek, clear, create, fit_zoom, set_playhead, tick

__all__ = ["TAG", "add_clip", "bind", "bind_clip_moved", "bind_delete", "bind_seek", "clear", "create", "refresh", "set_playhead", "tick"]

_editor = None
_last_project_id: int | None = None


def bind(editor, on_error=None) -> None:
    global _editor
    _editor = editor
    bind_seek(editor.seek)
    bind_delete(lambda clip: _bridge_delete(editor, clip))
    bind_clip_moved(lambda clip: _bridge_moved(editor, clip))


def refresh() -> None:
    global _last_project_id
    if _editor is None:
        return
    project_id = id(_editor.project)
    is_new_project = project_id != _last_project_id
    clear()
    for clip in _editor.project.timeline.clips:
        if isinstance(clip, MediaClip):
            add_clip(clip)
    if is_new_project:
        _last_project_id = project_id
        fit_zoom()


def _bridge_delete(editor, clip) -> None:
    editor.project.timeline.remove_clip(clip.id)
    if editor.selected_id == clip.id:
        editor.selected_id = None
    editor._edited()


def _bridge_moved(editor, clip) -> None:
    editor._edited()
