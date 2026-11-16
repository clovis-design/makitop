"""Zone « Propriétés » : réglages du clip, de l'effet ou du keyframe sélectionné."""

import dearpygui.dearpygui as dpg

from makitop.model.keyframes import INTERPOLATIONS, PROPERTIES
from makitop.model.timeline import ImageClip

TAG = "properties_panel"
_NO_EFFECT = "Aucun effet : choisissez-en dans la section Effets."
_HINT_COLOR = (150, 155, 175)
_editor = None
_on_error = None
# (clip, suite des effets) affichée : la liste n'est reconstruite que si elle change,
# pour ne pas interrompre le glissement d'un curseur.
_shown_effects = None


def effect_slider_tag(index: int) -> str:
    return f"clip_effect_{index}"


def create() -> None:
    global _editor, _shown_effects
    _editor, _shown_effects = None, None
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
            dpg.add_separator()
            dpg.add_text("Position / taille (% du cadre)")
            for name in ("x", "y", "width", "height"):
                with dpg.group(horizontal=True):
                    dpg.add_input_float(label=PROPERTIES[name][0], tag=f"clip_{name}",
                                        width=100, on_enter=True, user_data=name,
                                        callback=lambda s, v, p: _action(
                                            "set_animated_value", p, v / 100))
                    _key_button(name)
            with dpg.group(tag="clip_audio"):
                dpg.add_separator()
                with dpg.group(horizontal=True):
                    dpg.add_slider_float(label="Volume (%)", tag="clip_volume", width=120,
                                         min_value=0, max_value=200, format="%.0f",
                                         callback=lambda s, v: _update(volume=v / 100))
                    _key_button("volume")
                dpg.add_checkbox(label="Muet", tag="clip_muted",
                                 callback=lambda s, v: _update(muted=v))
            dpg.add_separator()
            dpg.add_text("Images clés")
            dpg.add_text("", tag="keyframe_cursor", wrap=260)
            dpg.add_text("+ clé : mémoriser la valeur à cet instant.\n"
                         "Une propriété animée crée une clé à chaque modification.",
                         wrap=260, color=_HINT_COLOR)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Précédente",
                               callback=lambda: _action("adjacent_keyframe", -1))
                dpg.add_button(label="Suivante", callback=lambda: _action("adjacent_keyframe", 1))
            dpg.add_text("Aucune clé sélectionnée", tag="keyframe_selected", wrap=260)
            with dpg.group(tag="keyframe_edit", show=False):
                dpg.add_input_float(label="Temps dans le clip (s)", tag="keyframe_time",
                                    width=100, format="%.4f", on_enter=True,
                                    callback=_key_time_changed)
                dpg.add_combo(list(INTERPOLATIONS), label="Vers la clé suivante",
                              tag="keyframe_interpolation", width=105,
                              callback=lambda s, v: _action(
                                  "set_keyframe_interpolation", INTERPOLATIONS[v]))
                dpg.add_button(label="Supprimer cette clé",
                               callback=lambda: _action("remove_keyframe"))
            with dpg.group(tag="clip_effects"):
                dpg.add_separator()
                dpg.add_text("Effets")
                dpg.add_text(_NO_EFFECT, tag="clip_effects_empty", wrap=260, color=_HINT_COLOR)
                dpg.add_group(tag="clip_effects_list")
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
    dpg.set_value("clip_muted", clip.muted)
    _refresh_effects(clip)
    tick(_editor.playback.current_time())
    selected = next((k for k in clip.keyframes
                     if (k.property, k.time) == _editor.selected_keyframe), None)
    dpg.configure_item("keyframe_edit", show=selected is not None)
    dpg.set_value("keyframe_selected", (
        f"{PROPERTIES[selected.property][0]} à {selected.time:.4f} s"
        if selected else "Aucune clé sélectionnée"
    ))
    if selected:
        dpg.set_value("keyframe_time", selected.time)
        label = next(k for k, v in INTERPOLATIONS.items() if v == selected.interpolation)
        dpg.set_value("keyframe_interpolation", label)


def _key_button(name):
    dpg.add_button(label="+ clé", tag=f"keyframe_add_{name}", user_data=name,
                   callback=lambda s, v, p: _action("toggle_keyframe", p))


def _key_time_changed(sender, value):
    if _editor is not None and _editor.selected_keyframe is not None:
        _action("move_keyframe", *_editor.selected_keyframe, value)


def tick(position):
    """Actualise les valeurs animées à la lecture/au seek, sans reconstruire les contrôles."""
    clip = _editor.selected if _editor and not _editor.source_mode else None
    if clip is None:
        return
    local_time = max(0, min(clip.duration, position - clip.timeline_start))
    transform = clip.transform_at(local_time)
    key_time = _editor.keyframe_time()
    for name in PROPERTIES:
        value = clip.volume_at(local_time) if name == "volume" else getattr(transform, name)
        tag = f"clip_{name}"
        if not dpg.is_item_active(tag) and dpg.get_value(tag) != value * 100:
            dpg.set_value(tag, value * 100)
        exists = any(k.property == name and abs(k.time - key_time) < 1e-9 for k in clip.keyframes)
        label = "- clé" if exists else "+ clé"
        if dpg.get_item_label(f"keyframe_add_{name}") != label:
            dpg.configure_item(f"keyframe_add_{name}", label=label)
    dpg.set_value("keyframe_cursor", f"Temps dans le clip : {local_time:.3f} s")


def _scale(spec) -> float:
    return 100 if spec.unit == "%" else 1


def _refresh_effects(clip):
    global _shown_effects
    kinds = tuple(e.kind for e in clip.effects)
    dpg.configure_item("clip_effects_empty", show=not kinds)
    if (clip.id, kinds) != _shown_effects:
        _shown_effects = (clip.id, kinds)
        dpg.delete_item("clip_effects_list", children_only=True)
        for index, effect in enumerate(clip.effects):
            _effect_row(index, effect.spec)
    for index, effect in enumerate(clip.effects):
        if dpg.does_item_exist(effect_slider_tag(index)):
            dpg.set_value(effect_slider_tag(index), effect.amount * _scale(effect.spec))


def _effect_row(index, spec):
    with dpg.group(horizontal=True, parent="clip_effects_list"):
        dpg.add_button(label="×", width=20, user_data=index,
                       callback=lambda s, a, i: _action("remove_effect", i))
        if not spec.adjustable:
            dpg.add_text(spec.label)
            return
        scale = _scale(spec)
        fmt = "%.0f %%" if spec.unit == "%" else "%.1f s"
        dpg.add_slider_float(label=spec.label, tag=effect_slider_tag(index), width=120,
                             min_value=spec.min * scale, max_value=spec.max * scale,
                             format=fmt, user_data=(index, scale), callback=_effect_changed)


def _effect_changed(sender, value, user_data):
    index, scale = user_data
    _action("update_effect", index, value / scale)


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
