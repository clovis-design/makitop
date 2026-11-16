"""Panneau timeline : API publique conservée pour l'assemblage de la fenêtre."""

from makitop.model.timeline import MediaClip
from makitop.ui.panels.timeline.panel import TAG, add_clip, bind_clip_moved, bind_delete, bind_seek, clear, create, set_playhead, tick

__all__ = ["TAG", "add_clip", "bind", "bind_clip_moved", "bind_delete", "bind_seek", "clear", "create", "refresh", "set_playhead", "tick"]

_editor = None


def bind(editor, on_error=None) -> None:
    global _editor
    _editor = editor
    bind_seek(editor.seek)
    bind_delete(lambda clip: _bridge_delete(editor, clip))
    bind_clip_moved(lambda clip: _bridge_moved(editor, clip))


def refresh() -> None:
    if _editor is None:
        return
    clear()
    for clip in _editor.project.timeline.clips:
        if isinstance(clip, MediaClip):
            add_clip(clip)


def _bridge_delete(editor, clip) -> None:
    editor.project.timeline.remove_clip(clip.id)
    if editor.selected_id == clip.id:
        editor.selected_id = None
    editor._edited()


def _bridge_moved(editor, clip) -> None:
    editor._edited()
