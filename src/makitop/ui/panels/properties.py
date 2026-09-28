"""Zone « Propriétés » : réglages du clip, de l'effet ou du keyframe sélectionné."""

import dearpygui.dearpygui as dpg
import os
from makitop.ui.assets.style import COLORS, FONT_INTER

from makitop.model.timeline import ImageClip

TAG = "properties_panel"
_editor = None
_on_error = None


def create() -> None:
    global _editor
    _editor = None
    with dpg.child_window(tag=TAG, border=False):
        dpg.add_text("Propriétés")
        dpg.add_separator()
        dpg.add_text("Sélectionnez un calque", tag="clip_name", wrap=280)
        with dpg.group(tag="clip_properties", show=False):
            dpg.add_input_int(label="Piste (1 = fond)", tag="clip_track", width=95,
                              min_value=1, max_value=100, min_clamped=True, max_clamped=True,
                              on_enter=True, callback=lambda s, v: _update(track=v - 1))
            with dpg.group(horizontal=True):
                dpg.add_button(label="Derrière", callback=lambda: _action("move_layer", -1))
                dpg.add_button(label="Devant", callback=lambda: _action("move_layer", 1))
            dpg.add_separator()
            dpg.add_input_float(label="Début montage (s)", tag="clip_start", width=95,
                                on_enter=True, callback=lambda s, v: _update(timeline_start=v))
            with dpg.group(tag="clip_source_bounds"):
                dpg.add_input_float(label="Entrée source (s)", tag="clip_in", width=95,
                                    on_enter=True, callback=lambda s, v: _update(source_start=v))
                dpg.add_input_float(label="Sortie source (s)", tag="clip_out", width=95,
                                    on_enter=True, callback=lambda s, v: _update(source_end=v))
            dpg.add_input_float(label="Durée image (s)", tag="clip_image_duration", width=95,
                                on_enter=True, callback=lambda s, v: _update(display_duration=v))
            with dpg.group(tag="clip_audio"):
                dpg.add_separator()
                dpg.add_slider_float(label="Volume (%)", tag="clip_volume", width=160,
                                     min_value=0, max_value=200, format="%.0f",
                                     callback=lambda s, v: _update(volume=v / 100))
                dpg.add_checkbox(label="Muet", tag="clip_muted",
                                 callback=lambda s, v: _update(muted=v))
            dpg.add_separator()
            dpg.add_text("Déplacez le calque et ses poignées dans le cadre.", wrap=260)
            dpg.add_button(label="Réinitialiser taille / recadrage",
                           callback=lambda: _action("reset_transform"))
            dpg.add_button(label="Supprimer le calque", tag="clip_remove",
                           callback=lambda: _action("remove_selected"))


def bind(editor, on_error):
    global _editor, _on_error
    _editor, _on_error = editor, on_error
    refresh()


def refresh():
    clip = _editor.selected if _editor else None
    dpg.configure_item("clip_properties", show=clip is not None)
    dpg.set_value("clip_name", clip.media.name if clip else "Sélectionnez un calque")
    if clip is None:
        return
    is_image = isinstance(clip, ImageClip)
    dpg.set_value("clip_track", clip.track + 1)
    dpg.set_value("clip_start", clip.timeline_start)
    dpg.configure_item("clip_source_bounds", show=not is_image)
    dpg.configure_item("clip_image_duration", show=is_image)
    if is_image:
        dpg.set_value("clip_image_duration", clip.display_duration)
    else:
        dpg.set_value("clip_in", clip.source_start)
        dpg.set_value("clip_out", clip.source_end)
    dpg.configure_item("clip_audio", show=clip.media.has_audio and not is_image)
    dpg.set_value("clip_volume", clip.volume * 100)
    dpg.set_value("clip_muted", clip.muted)


def _update(**changes):
    if _editor is not None and _editor.selected is not None:
        _action("update_clip", _editor.selected_id, **changes)


def _action(method, *args, **kwargs):
    if _editor is None:
        return
    try:
        getattr(_editor, method)(*args, **kwargs)
    except (ValueError, KeyError, StopIteration) as exc:
        refresh()
        if _on_error:
            _on_error(str(exc))
