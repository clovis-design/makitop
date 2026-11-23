"""Panneau timeline : API publique conservée pour l'assemblage de la fenêtre."""

from makitop.ui.panels.timeline.panel import (
    TAG,
    add_clip,
    bind_clip_moved,
    bind_delete,
    bind_get_dragging_media,
    bind_keyframes,
    bind_media_drop,
    bind_seek,
    bind_select,
    bind_track_reordered,
    bind_zoom,
    clear,
    create,
    fit_zoom,
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
    bind_clip_moved(lambda clip: _bridge_drag(editor, clip))
    bind_track_reordered(lambda: _bridge_reorder(editor))
    bind_select(lambda clip: editor.select(clip.id))
    bind_zoom(editor.set_timeline_zoom)
    bind_get_dragging_media(media_panel.get_dragging_media)
    bind_media_drop(lambda media, start, row: _bridge_media_drop(editor, media, start, row))

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
    if is_new_project:
        _last_project_id = project_id
        saved_zoom = _editor.project.view.timeline_zoom
        from makitop.model.project import DEFAULT_TIMELINE_ZOOM
        if saved_zoom != DEFAULT_TIMELINE_ZOOM:
            set_zoom(saved_zoom)
        else:
            fit_zoom()


def _bridge_delete(editor, clip) -> None:
    editor.project.timeline.remove_clip(clip.id)
    if editor.selected_id == clip.id:
        editor.selected_id = None
        editor.selected_keyframe = None
    editor._edited()


def _bridge_drag(editor, clip) -> None:
    """Le clip a déjà été modifié en place (timeline_start mis à jour)."""
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


def _bridge_reorder(editor) -> None:
    """Réordonnancement de pistes via ▲/▼ : met à jour track et l'ordre des clips."""
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
