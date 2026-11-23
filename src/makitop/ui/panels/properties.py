"""Zone « Propriétés » : inspecteur du calque sélectionné (inspiré de DaVinci Resolve).

En-tête (nom et type du clip), onglets Vidéo / Audio / Effets, sections repliables
avec un bouton de réinitialisation, et lignes « libellé à gauche, valeur à droite ».
"""

from contextlib import contextmanager
from dataclasses import replace

import dearpygui.dearpygui as dpg

from makitop.model.composition import (
    center_offset,
    fitted_bounds,
    with_center_offset,
    with_crop,
)
from makitop.model.keyframes import INTERPOLATIONS, PROPERTIES
from makitop.model.media import MediaKind
from makitop.model.timeline import ImageClip
from makitop.ui.assets.style import COLORS
from makitop.ui.panels import inspector_icons

TAG = "properties_panel"
TABS = "clip_tabs"
TAB_VIDEO = "clip_tab_video"
TAB_AUDIO = "clip_tab_audio"
TAB_EFFECTS = "clip_tab_effects"
PANEL_THEME = "inspector_theme"
HEADER_THEME = "inspector_header_theme"
DANGER_THEME = "inspector_danger_theme"
_EMPTY = "Sélectionnez un calque"
_NO_EFFECT = "Aucun effet : choisissez-en dans la section Effets."
_KINDS = {MediaKind.VIDEO: "Vidéo", MediaKind.AUDIO: "Audio", MediaKind.IMAGE: "Image"}
_CROP_SIDES = (("left", "Gauche"), ("top", "Haut"), ("right", "Droite"), ("bottom", "Bas"))
_LABEL_W = 92
_ICON_PAD = 5
_editor = None
_on_error = None
# (clip, suite des effets) affichée : la liste n'est reconstruite que si elle change,
# pour ne pas interrompre le glissement d'un curseur.
_shown_effects = None
# Sections repliées (clé de section), conservées tant que l'application tourne.
_collapsed: set[str] = set()


def effect_slider_tag(index: int) -> str:
    return f"clip_effect_{index}"


def _content_tag(key: str) -> str:
    return f"inspector_section_{key}"


def _chevron_tag(key: str) -> str:
    return f"inspector_chevron_{key}"


# --- Construction ---------------------------------------------------------------

def create() -> None:
    global _editor, _shown_effects
    _editor, _shown_effects = None, None
    inspector_icons.load_textures()
    _themes()
    with dpg.child_window(tag=TAG, border=False):
        dpg.add_text("Sélectionnez un calque", tag="clip_name", wrap=0)
        dpg.add_text("", tag="clip_subtitle", color=COLORS["label_muted"], show=False)
        if dpg.does_alias_exist("small_text_font"):
            dpg.bind_item_font("clip_subtitle", "small_text_font")
        with dpg.group(tag="clip_properties", show=False):
            dpg.add_spacer(height=2)
            with dpg.tab_bar(tag=TABS):
                with dpg.tab(label="Vidéo", tag=TAB_VIDEO):
                    _video_tab()
                with dpg.tab(label="Audio", tag=TAB_AUDIO):
                    _audio_tab()
                with dpg.tab(label="Effets", tag=TAB_EFFECTS):
                    _effects_tab()
                with dpg.tab(label="Images clés", tag="clip_tab_keyframes"):
                    _keyframes_tab()
            dpg.add_spacer(height=4)
            dpg.add_button(label="Supprimer le calque", tag="clip_remove", width=-1, height=26,
                           callback=lambda: _action("remove_selected"))
            dpg.bind_item_theme("clip_remove", DANGER_THEME)
    dpg.bind_item_theme(TAG, PANEL_THEME)


def _video_tab() -> None:
    with dpg.group(tag="clip_geometry"):
        with _section("transform", "Transformation", on_reset=lambda: _action("reset_transform")):
            with _rows():
                with _row("Zoom"):
                    _drag("clip_zoom", 1, 800, lambda s, v: _set_zoom(v))
                with _row("Position X"):
                    _drag("clip_pos_x", -800, 800, lambda s, v: _set_position(x=v))
                with _row("Position Y"):
                    _drag("clip_pos_y", -800, 800, lambda s, v: _set_position(y=v))
        with _section("crop", "Recadrage", on_reset=_reset_crop):
            with _rows():
                for side, label in _CROP_SIDES:
                    with _row(label):
                        _drag(f"clip_crop_{side}", 0, 98, _crop_changed, user_data=side)
    with _section("timing", "Temps"):
        with _rows():
            with _row("Début (s)"):
                dpg.add_input_float(tag="clip_start", width=-1, step=0, format="%.2f",
                                    on_enter=True, callback=lambda s, v: _update(timeline_start=v))
            with _row("Entrée (s)", tag="clip_in_row"):
                dpg.add_input_float(tag="clip_in", width=-1, step=0, format="%.2f",
                                    on_enter=True, callback=lambda s, v: _update(source_start=v))
            with _row("Sortie (s)", tag="clip_out_row"):
                dpg.add_input_float(tag="clip_out", width=-1, step=0, format="%.2f",
                                    on_enter=True, callback=lambda s, v: _update(source_end=v))
            with _row("Durée (s)", tag="clip_image_duration_row"):
                dpg.add_input_float(tag="clip_image_duration", width=-1, step=0, format="%.2f",
                                    on_enter=True,
                                    callback=lambda s, v: _update(display_duration=v))
    with _section("layer", "Calque"):
        with _rows():
            with _row("Piste"):
                dpg.add_input_int(tag="clip_track", width=-1, step=0, min_value=1,
                                  max_value=100, min_clamped=True, max_clamped=True,
                                  on_enter=True, callback=lambda s, v: _update(track=v - 1))
                with dpg.tooltip("clip_track"):
                    dpg.add_text("1 = fond, les pistes plus hautes passent devant.")
            with _row("Ordre"):
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Derrière", callback=lambda: _action("move_layer", -1))
                    dpg.add_button(label="Devant", callback=lambda: _action("move_layer", 1))


def _audio_tab() -> None:
    with dpg.group(tag="clip_audio"):
        with _section("volume", "Volume", on_reset=lambda: _update(volume=1.0, muted=False)):
            with _rows():
                with _row("Volume"):
                    dpg.add_slider_float(tag="clip_volume", width=-1, min_value=0,
                                         max_value=200, format="%.0f %%",
                                         callback=lambda s, v: _update(volume=v / 100))
                with _row("Muet"):
                    dpg.add_checkbox(tag="clip_muted", callback=lambda s, v: _update(muted=v))


def _effects_tab() -> None:
    with dpg.group(tag="clip_effects"):
        dpg.add_text(_NO_EFFECT, tag="clip_effects_empty", wrap=0, color=COLORS["label_muted"])
        dpg.add_group(tag="clip_effects_list")


def _keyframes_tab() -> None:
    dpg.add_text("", tag="keyframe_cursor", wrap=0, color=COLORS["label_muted"])
    dpg.add_text("Placez la tête de lecture, puis cliquez sur ◇",
                 color=COLORS["label_muted"])
    dpg.add_text("pour poser une clé sur la propriété souhaitée.",
                 color=COLORS["label_muted"])
    dpg.add_spacer(height=3)
    with _section("kf_props", "Propriétés animées"), _rows():
        for name in ("x", "y", "zoom", "width", "height"):
            with _row(PROPERTIES[name][0], tag=f"keyframe_row_{name}"):
                _key_button(name)
        with _row(PROPERTIES["volume"][0], tag="keyframe_row_volume"):
            _key_button("volume")
    with _section("kf_edit", "Clé sélectionnée"):
        with dpg.group(horizontal=True):
            dpg.add_button(label="◀ Préc.", callback=lambda: _action("adjacent_keyframe", -1))
            dpg.add_button(label="Suiv. ▶", callback=lambda: _action("adjacent_keyframe", 1))
        dpg.add_spacer(height=4)
        dpg.add_text("Sélectionnez une clé sur la timeline.", tag="keyframe_selected",
                     wrap=0, color=COLORS["label_muted"])
        with dpg.group(tag="keyframe_edit", show=False):
            with _rows():
                with _row("Valeur"):
                    dpg.add_input_float(tag="keyframe_value", width=-1, step=0, format="%.1f %%",
                                        on_enter=True,
                                        callback=lambda s, v: _action(
                                            "set_selected_keyframe_value", v / 100))
                with _row("Temps (s)"):
                    dpg.add_input_float(tag="keyframe_time", width=-1, step=0, format="%.4f",
                                        on_enter=True, callback=_key_time_changed)
                with _row("Interpolation"):
                    dpg.add_combo(list(INTERPOLATIONS), tag="keyframe_interpolation", width=-1,
                                  callback=lambda s, v: _action(
                                      "set_keyframe_interpolation", INTERPOLATIONS[v]))


@contextmanager
def _section(key, title, on_reset=None, icon="reset"):
    """En-tête repliable (chevron + titre + bouton d'action) puis son contenu."""
    is_open = key not in _collapsed
    with dpg.group(horizontal=True, horizontal_spacing=0) as header:
        dpg.add_image_button(
            inspector_icons.texture_tag("chevron_down" if is_open else "chevron_right"),
            tag=_chevron_tag(key), user_data=key, callback=_toggle)
        icon_w = inspector_icons.ICON_SIZE + 2 * _ICON_PAD
        dpg.add_button(label=title, width=-icon_w if on_reset else -1, user_data=key,
                       callback=_toggle)
        if on_reset:
            dpg.add_image_button(inspector_icons.texture_tag(icon), callback=lambda: on_reset())
    dpg.bind_item_theme(header, HEADER_THEME)
    with dpg.group(tag=_content_tag(key), show=is_open, indent=4):
        yield
    dpg.add_spacer(height=3)


@contextmanager
def _rows():
    with dpg.table(header_row=False, pad_outerX=False):
        dpg.add_table_column(width_fixed=True, init_width_or_weight=_LABEL_W)
        dpg.add_table_column(width_stretch=True)
        yield


@contextmanager
def _row(label, tag=0):
    with dpg.table_row(tag=tag):
        dpg.add_text(label, color=COLORS["label_muted"])
        with dpg.group():
            yield


def _drag(tag, low, high, callback, user_data=None):
    dpg.add_drag_float(tag=tag, width=-1, speed=0.25, min_value=low, max_value=high,
                       clamped=True, format="%.1f %%", callback=callback, user_data=user_data)


def _toggle(sender, app_data, key):
    is_open = key in _collapsed
    if is_open:
        _collapsed.discard(key)
    else:
        _collapsed.add(key)
    dpg.configure_item(_content_tag(key), show=is_open)
    dpg.configure_item(_chevron_tag(key), texture_tag=inspector_icons.texture_tag(
        "chevron_down" if is_open else "chevron_right"))


def _themes() -> None:
    if dpg.does_alias_exist(PANEL_THEME):
        return
    with dpg.theme(tag=PANEL_THEME):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 6, 3)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 6, 4)
            dpg.add_theme_style(dpg.mvStyleVar_CellPadding, 4, 2)
            dpg.add_theme_style(dpg.mvStyleVar_TabRounding, 3)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, COLORS["field_bg"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, COLORS["field_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, COLORS["field_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, COLORS["accent"])
            dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, COLORS["accent_active"])
            dpg.add_theme_color(dpg.mvThemeCol_CheckMark, COLORS["accent_active"])
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["section_header"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLORS["accent"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, COLORS["accent_active"])
            dpg.add_theme_color(dpg.mvThemeCol_Tab, COLORS["section_header"])
            dpg.add_theme_color(dpg.mvThemeCol_TabHovered, COLORS["accent"])
            dpg.add_theme_color(dpg.mvThemeCol_TabActive, COLORS["accent"])
            dpg.add_theme_color(dpg.mvThemeCol_Separator, COLORS["section_header"])
    with dpg.theme(tag=HEADER_THEME):
        with dpg.theme_component(dpg.mvImageButton):
            # Même hauteur que le bouton titre : icône + 2 × marge = police + 2 × 4.
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, _ICON_PAD, _ICON_PAD)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 0)
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["section_header"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLORS["section_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, COLORS["section_hover"])
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 0)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 6, 4)
            dpg.add_theme_style(dpg.mvStyleVar_ButtonTextAlign, 0, 0.5)
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["section_header"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLORS["section_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, COLORS["section_hover"])
    with dpg.theme(tag=DANGER_THEME):
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLORS["danger"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLORS["danger_hover"])
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, COLORS["danger_hover"])


# --- Synchronisation ------------------------------------------------------------

def bind(editor, on_error):
    global _editor, _on_error
    _editor, _on_error = editor, on_error
    refresh()


def refresh():
    clip = _editor.selected if _editor else None
    dpg.configure_item("clip_properties", show=clip is not None)
    dpg.configure_item("clip_subtitle", show=clip is not None)
    dpg.set_value("clip_name", clip.media.name if clip else _EMPTY)
    if clip is None:
        return
    is_image = isinstance(clip, ImageClip)
    dpg.set_value("clip_subtitle", _subtitle(clip))
    dpg.set_value("clip_track", clip.track + 1)
    dpg.set_value("clip_start", clip.timeline_start)
    for row in ("clip_in_row", "clip_out_row"):
        dpg.configure_item(row, show=not is_image)
    dpg.configure_item("clip_image_duration_row", show=is_image)
    if is_image:
        dpg.set_value("clip_image_duration", clip.display_duration)
    else:
        dpg.set_value("clip_in", clip.source_start)
        dpg.set_value("clip_out", clip.source_end)
    dpg.configure_item("clip_geometry", show=clip.media.kind != MediaKind.AUDIO)
    for name in ("x", "y", "zoom", "width", "height"):
        dpg.configure_item(f"keyframe_row_{name}", show=clip.media.kind != MediaKind.AUDIO)
    dpg.configure_item("keyframe_row_volume", show=clip.media.has_audio and not is_image)
    _refresh_geometry(clip.transform)
    has_audio = clip.media.has_audio and not is_image
    dpg.configure_item(TAB_AUDIO, show=has_audio)
    if not has_audio and dpg.get_value(TABS) in (TAB_AUDIO, dpg.get_alias_id(TAB_AUDIO)):
        dpg.set_value(TABS, dpg.get_alias_id(TAB_VIDEO))
    dpg.set_value("clip_volume", clip.volume * 100)
    dpg.set_value("clip_muted", clip.muted)
    _refresh_effects(clip)
    tick(_editor.playback.current_time())
    if dpg.does_alias_exist("keyframe_edit"):
        selected = next((k for k in clip.keyframes
                         if (k.property, k.time) == _editor.selected_keyframe), None)
        dpg.configure_item("keyframe_edit", show=selected is not None)
        if dpg.does_alias_exist("keyframe_selected"):
            dpg.set_value("keyframe_selected", (
                f"{PROPERTIES[selected.property][0]} · {selected.time:.3f} s"
                if selected else "Sélectionnez une clé sur la timeline."
            ))
        if selected:
            dpg.set_value("keyframe_value", selected.value * 100)
            if dpg.does_alias_exist("keyframe_time"):
                dpg.set_value("keyframe_time", selected.time)
            if dpg.does_alias_exist("keyframe_interpolation"):
                label = next(k for k, v in INTERPOLATIONS.items() if v == selected.interpolation)
                dpg.set_value("keyframe_interpolation", label)


def _key_button(name):
    dpg.add_button(label="◇", tag=f"keyframe_add_{name}", width=30, user_data=name,
                   callback=lambda s, v, p: _action("toggle_keyframe", p))
    with dpg.tooltip(f"keyframe_add_{name}"):
        dpg.add_text("", tag=f"keyframe_hint_{name}")


def _key_time_changed(sender, value):
    if _editor is not None and _editor.selected_keyframe is not None:
        _action("move_keyframe", *_editor.selected_keyframe, value)


def tick(position):
    """Actualise les indicateurs de clés et la position sans reconstruire les contrôles."""
    clip = _editor.selected if _editor and not _editor.source_mode else None
    if clip is None:
        return
    local_time = max(0, min(clip.duration, position - clip.timeline_start))
    key_time = _editor.keyframe_time()
    for name in PROPERTIES:
        key_tag = f"keyframe_add_{name}"
        if dpg.does_alias_exist(key_tag):
            exists = any(k.property == name and abs(k.time - key_time) < 1e-9
                         for k in clip.keyframes)
            label = "◆" if exists else "◇"
            if dpg.get_item_label(key_tag) != label:
                dpg.configure_item(key_tag, label=label)
            hint = ("Retirer" if exists else "Ajouter") + (
                f" une clé « {PROPERTIES[name][0]} » à {key_time:.3f} s"
            )
            if dpg.get_value(f"keyframe_hint_{name}") != hint:
                dpg.set_value(f"keyframe_hint_{name}", hint)
    if dpg.does_alias_exist("keyframe_cursor"):
        count = len(clip.keyframes)
        cursor = f"Clip : {local_time:.3f} s  ·  {count} clé{'s' if count != 1 else ''}"
        if dpg.get_value("keyframe_cursor") != cursor:
            dpg.set_value("keyframe_cursor", cursor)
    if not dpg.is_item_active("clip_zoom"):
        zoom = clip.transform_at(local_time).width * 100
        if dpg.get_value("clip_zoom") != zoom:
            dpg.set_value("clip_zoom", zoom)


def _subtitle(clip) -> str:
    media = clip.media
    parts = [_KINDS.get(media.kind, "Média")]
    if media.width and media.height:
        parts.append(f"{media.width}×{media.height}")
    parts.append(f"{clip.duration:.1f} s")
    return "  ·  ".join(parts)


def _refresh_geometry(t) -> None:
    cx, cy = center_offset(t)
    dpg.set_value("clip_zoom", t.width * 100)
    dpg.set_value("clip_pos_x", cx * 100)
    dpg.set_value("clip_pos_y", cy * 100)
    for side, _ in _CROP_SIDES:
        dpg.set_value(f"clip_crop_{side}", getattr(t, f"crop_{side}") * 100)


def _subtitle(clip) -> str:
    media = clip.media
    parts = [_KINDS.get(media.kind, "Média")]
    if media.width and media.height:
        parts.append(f"{media.width}×{media.height}")
    parts.append(f"{clip.duration:.1f} s")
    return "  ·  ".join(parts)


def _refresh_geometry(t) -> None:
    cx, cy = center_offset(t)
    dpg.set_value("clip_zoom", t.width * 100)
    dpg.set_value("clip_pos_x", cx * 100)
    dpg.set_value("clip_pos_y", cy * 100)
    for side, _ in _CROP_SIDES:
        dpg.set_value(f"clip_crop_{side}", getattr(t, f"crop_{side}") * 100)


def _scale(spec) -> float:
    return 100 if spec.unit == "%" else 1


def _refresh_effects(clip):
    global _shown_effects
    kinds = tuple(e.kind for e in clip.effects)
    dpg.configure_item("clip_effects_empty", show=not kinds)
    if (clip.id, kinds) != _shown_effects:
        added = (_shown_effects is not None and _shown_effects[0] == clip.id
                 and len(kinds) > len(_shown_effects[1]))
        _shown_effects = (clip.id, kinds)
        dpg.delete_item("clip_effects_list", children_only=True)
        for index, effect in enumerate(clip.effects):
            _effect_row(index, effect.spec)
        if added:
            dpg.set_value(TABS, dpg.get_alias_id(TAB_EFFECTS))
    for index, effect in enumerate(clip.effects):
        if dpg.does_item_exist(effect_slider_tag(index)):
            dpg.set_value(effect_slider_tag(index), effect.amount * _scale(effect.spec))


def _effect_row(index, spec):
    with dpg.group(parent="clip_effects_list"):
        with _section(f"effect_{index}", spec.label, icon="close",
                      on_reset=lambda: _action("remove_effect", index)):
            if not spec.adjustable:
                return
            scale = _scale(spec)
            fmt = "%.0f %%" if spec.unit == "%" else "%.1f s"
            with _rows():
                with _row("Intensité" if spec.unit == "%" else "Durée"):
                    dpg.add_slider_float(tag=effect_slider_tag(index), width=-1,
                                         min_value=spec.min * scale,
                                         max_value=spec.max * scale, format=fmt,
                                         user_data=(index, scale), callback=_effect_changed)


# --- Modifications --------------------------------------------------------------

def _effect_changed(sender, value, user_data):
    index, scale = user_data
    _action("update_effect", index, value / scale)


def _set_zoom(percent):
    if _selected() is not None:
        _action("set_animated_value", "zoom", percent / 100)


def _set_position(x=None, y=None):
    clip = _selected()
    if clip is None:
        return
    cx, cy = center_offset(clip.transform)
    cx = cx if x is None else x / 100
    cy = cy if y is None else y / 100
    _transform(lambda: with_center_offset(clip.transform, cx, cy))


def _bounds(clip, transform):
    return fitted_bounds(transform, clip.media.width, clip.media.height,
                         _editor.project.canvas_ratio)


def _crop_changed(sender, percent, side):
    clip = _selected()
    if clip is not None:
        _transform(lambda: with_crop(clip.transform, _bounds(clip, clip.transform),
                                     side, percent / 100))


def _reset_crop():
    clip = _selected()
    if clip is None:
        return

    def uncropped():
        t = clip.transform
        for side, _ in _CROP_SIDES:
            t = with_crop(t, _bounds(clip, t), side, 0)
        return replace(t, crop_left=0, crop_top=0, crop_right=0, crop_bottom=0)
    _transform(uncropped)


def _transform(build):
    """Calcule la nouvelle géométrie ; une valeur hors bornes est signalée sans rien changer."""
    try:
        transform = build()
    except ValueError as exc:
        refresh()
        if _on_error:
            _on_error(str(exc))
        return
    _update(transform=transform)


def _selected():
    return _editor.selected if _editor is not None else None


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
