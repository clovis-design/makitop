"""Panneau timeline : API publique conservée pour l'assemblage de la fenêtre."""

from makitop.ui.panels.timeline.panel import (
    TAG,
    add_clip,
    bind_clip_moved,
    bind_clip_drag_start,
    bind_copy,
    bind_undo,
    bind_redo,
    update_undo_redo_buttons,
    bind_cut,
    bind_delete,
    bind_duplicate,
    bind_paste,
    bind_split,
    bind_get_dragging_media,
    bind_get_dragging_text,
    bind_keyframes,
    bind_media_drop,
    bind_text_drop,
    bind_seek,
    bind_select,
    bind_track_reordered,
    bind_zoom,
    clear,
    create,
    delete_selected,
    fit_zoom,
    toggle_keyframes,
    zoom_in,
    zoom_out,
    get_clip_ids,
    get_track_rows,
    set_clips,
    set_playhead,
    set_zoom,
    tick,
)

__all__ = [
    "TAG", "add_clip", "bind", "bind_clip_moved", "bind_delete", "bind_seek",
    "clear", "create", "get_clip_ids", "refresh", "set_playhead", "tick",
]

_editor = None
_last_project_id: int | None = None


def bind(editor, on_error=None) -> None:
    global _editor
    _editor = editor
    from makitop.ui.panels import media as media_panel
    bind_seek(editor.seek)
    bind_delete(lambda clip: _bridge_delete(editor, clip))
    bind_split(editor.split_at_playhead)
    bind_duplicate(editor.duplicate_selected)
    bind_clip_drag_start(lambda: _bridge_drag_start(editor))
    bind_undo(editor.undo)
    bind_redo(editor.redo)
    bind_copy(editor.copy_selected)
    bind_cut(editor.cut_selected)
    bind_paste(editor.paste_clip)
    bind_clip_moved(lambda clip: _bridge_drag(editor, clip))
    bind_track_reordered(lambda: _bridge_reorder(editor))
    bind_select(lambda clip: editor.select(clip.id))
    bind_zoom(editor.set_timeline_zoom)
    bind_get_dragging_media(media_panel.get_dragging_media)
    bind_media_drop(lambda media, start, row: _bridge_media_drop(editor, media, start, row))
    from makitop.ui.panels import text_presets
    bind_get_dragging_text(text_presets.get_dragging_text)
    bind_text_drop(lambda kind, start: _bridge_text_drop(editor, kind, start))

    def key_action(method, *args):
        try:
            getattr(editor, method)(*args)
        except (ValueError, KeyError, StopIteration) as exc:
            if on_error:
                on_error(str(exc))
            refresh()

    def move_key(property, old_time, new_time):
        fps = editor.project.timeline.fps
        new_time = min(editor.selected.duration, round(new_time * fps) / fps)
        key_action("move_keyframe", property, old_time, new_time)

    bind_keyframes(
        lambda *args: key_action("select_keyframe", *args), move_key,
    )


def refresh() -> None:
    global _last_project_id
    if _editor is None:
        return
    project_id = id(_editor.project)
    is_new_project = project_id != _last_project_id
    set_clips(_editor.project.timeline.clips, _editor.selected_id, _editor.selected_keyframe)
    update_undo_redo_buttons(_editor.can_undo, _editor.can_redo)
    if is_new_project:
        _last_project_id = project_id
        fit_zoom()


def undo() -> None:
    if _editor is not None:
        _editor.undo()


def redo() -> None:
    if _editor is not None:
        _editor.redo()


def split_at_playhead() -> None:
    if _editor is not None:
        _editor.split_at_playhead()


def duplicate_selected() -> None:
    if _editor is not None:
        _editor.duplicate_selected()


def copy_selected() -> None:
    if _editor is not None:
        _editor.copy_selected()


def cut_selected() -> None:
    if _editor is not None:
        _editor.cut_selected()


def paste_clip() -> None:
    if _editor is not None:
        _editor.paste_clip()


def _bridge_delete(editor, clip) -> None:
    editor.push_undo()
    editor.project.timeline.remove_clip(clip.id)
    if editor.selected_id == clip.id:
        editor.selected_id = None
        editor.selected_keyframe = None
    editor._edited()


def _bridge_drag(editor, clip) -> None:
    """Le clip a déjà été modifié en place (timeline_start mis à jour).
    L'undo a été poussé par _bridge_drag_start au début du drag."""
    editor._edited()


def _bridge_media_drop(editor, media, start: float, target_row: int) -> None:
    """Crée un clip à la position de drop et insère la nouvelle piste à target_row."""
    from makitop.ui.panels.timeline.panel import move_track_to
    try:
        clip = editor.add_media(media, start)
        rows = get_track_rows()
        source_row = next(i for i, row in enumerate(rows) if clip.id in row)
        clamped = min(max(source_row, target_row), len(rows) - 1)
        if clamped > source_row:
            move_track_to(source_row, clamped)
            _bridge_reorder(editor)
    except ValueError:
        pass


def _bridge_text_drop(editor, kind: str, start: float) -> None:
    try:
        editor.add_text(kind, start=start)
    except ValueError:
        pass


def _bridge_drag_start(editor) -> None:
    editor.push_undo()


def _bridge_reorder(editor) -> None:
    """Réordonnancement de pistes via ▲/▼ : met à jour track et l'ordre des clips."""
    editor.push_undo()
    track_rows = get_track_rows()  # list[list[str]], haut → bas
    id_to_clip = {c.id: c for c in editor.project.timeline.clips}
    for track, row_ids in enumerate(reversed(track_rows)):
        for cid in row_ids:
            if cid in id_to_clip:
                id_to_clip[cid].track = min(track, 99)
    # Synchroniser l'ordre de editor.project.timeline.clips
    all_ids = [cid for row in track_rows for cid in row]
    panel_set = set(all_ids)
    new_order = [id_to_clip[cid] for cid in all_ids if cid in id_to_clip]
    new_order += [c for c in editor.project.timeline.clips if c.id not in panel_set]
    editor.project.timeline.clips[:] = new_order
    editor._edited()
