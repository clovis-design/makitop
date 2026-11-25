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
from makitop.model.keyframes import GEOMETRY_PROPERTIES, INTERPOLATIONS, PROPERTIES
from makitop.model.media import MediaKind
from makitop.model.text import ALIGNMENTS, FONTS, MAX_TEXT_LENGTH
from makitop.model.timeline import MAX_CLIP_SPEED, MIN_CLIP_SPEED, ImageClip, TextClip
from makitop.ui.assets.style import COLORS
from makitop.ui.panels import inspector_icons

TAG = "properties_panel"
TABS = "clip_tabs"
TAB_VIDEO = "clip_tab_video"
TAB_AUDIO = "clip_tab_audio"
TAB_EFFECTS = "clip_tab_effects"
TAB_KEYFRAMES = "clip_tab_keyframes"
TAB_TEXT = "clip_tab_text"
TEXT_CONTENT = "clip_text_content"
PANEL_THEME = "inspector_theme"
HEADER_THEME = "inspector_header_theme"
DANGER_THEME = "inspector_danger_theme"
ANIMATED_FIELD_THEME = "inspector_animated_field_theme"
_EMPTY = "Sélectionnez un calque"
_NO_EFFECT = "Aucun effet : choisissez-en dans la section Effets."
_KINDS = {MediaKind.VIDEO: "Vidéo", MediaKind.AUDIO: "Audio", MediaKind.IMAGE: "Image"}
_CROP_SIDES = (("left", "Gauche"), ("top", "Haut"), ("right", "Droite"), ("bottom", "Bas"))
_TEXT_BOX_FIELDS = (("x", "Position X"), ("y", "Position Y"),
                    ("width", "Largeur"), ("height", "Hauteur"))
_SPEED_PRESETS = (MIN_CLIP_SPEED, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0, 6.0, MAX_CLIP_SPEED)
_ANIMATION_HINT = "◆ Animé : cliquez sur la valeur pour ouvrir sa clé."
_GEOMETRY_KEYS = frozenset(GEOMETRY_PROPERTIES)
_ANIMATED_CONTROLS = {
    "clip_zoom": _GEOMETRY_KEYS,  # Le zoom redimensionne et recentre le calque.
    "clip_pos_x": {"x", "width"},
    "clip_pos_y": {"y", "height"},
    **{f"clip_crop_{side}": _GEOMETRY_KEYS for side, _ in _CROP_SIDES},
    "inspector_reset_transform": _GEOMETRY_KEYS,
    "inspector_reset_crop": _GEOMETRY_KEYS,
    "clip_volume": {"volume"},
    "inspector_reset_volume": {"volume"},
    "clip_text_x": {"x"},
    "clip_text_y": {"y"},
    "clip_text_width": {"width", "zoom"},
    "clip_text_height": {"height", "zoom"},
}
_PRIMARY_KEYS = {
    "clip_zoom": "zoom", "clip_pos_x": "x", "clip_pos_y": "y", "clip_volume": "volume",
    **{f"clip_text_{field}": field for field, _ in _TEXT_BOX_FIELDS},
}
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
                with dpg.tab(label="Texte", tag=TAB_TEXT, show=False):
                    _text_tab()
                with dpg.tab(label="Images clés", tag=TAB_KEYFRAMES):
                    _keyframes_tab()
            dpg.add_spacer(height=4)
            dpg.add_button(label="Supprimer le calque", tag="clip_remove", width=-1, height=26,
                           callback=lambda: _action("remove_selected"))
            dpg.bind_item_theme("clip_remove", DANGER_THEME)
    dpg.bind_item_theme(TAG, PANEL_THEME)


def _video_tab() -> None:
    with dpg.group(tag="clip_geometry"):
        _animation_hint("video")
        with _section("transform", "Transformation", on_reset=lambda: _action("reset_transform")):
            with _rows():
                with _animated_row("Zoom", "clip_zoom"):
                    _drag("clip_zoom", 1, 800, lambda s, v: _set_zoom(v))
                with _animated_row("Position X", "clip_pos_x"):
                    _drag("clip_pos_x", -800, 800, lambda s, v: _set_position(x=v))
                with _animated_row("Position Y", "clip_pos_y"):
                    _drag("clip_pos_y", -800, 800, lambda s, v: _set_position(y=v))
                with _row("Rotation"):
                    dpg.add_slider_float(tag="clip_rotation", width=-1, min_value=-180,
                                         max_value=180, format="%.1f°", clamped=True,
                                         callback=lambda s, v: _action(
                                             "set_clip_orientation", rotation=v))
                    with dpg.tooltip("clip_rotation"):
                        dpg.add_text("Vous pouvez aussi tirer la poignée ronde dans le lecteur.")
                with _row("Miroir"), dpg.group(horizontal=True):
                    dpg.add_checkbox(label="Horizontal", tag="clip_flip_horizontal",
                                     callback=lambda s, v: _action(
                                         "set_clip_orientation", flip_horizontal=v))
                    with dpg.tooltip("clip_flip_horizontal"):
                        dpg.add_text("Échange la gauche et la droite de l’image.")
                    dpg.add_checkbox(label="Vertical", tag="clip_flip_vertical",
                                     callback=lambda s, v: _action(
                                         "set_clip_orientation", flip_vertical=v))
                    with dpg.tooltip("clip_flip_vertical"):
                        dpg.add_text("Échange le haut et le bas de l’image.")
        with _section("crop", "Recadrage", on_reset=_reset_crop):
            with _rows():
                for side, label in _CROP_SIDES:
                    with _animated_row(label, f"clip_crop_{side}"):
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
            with _row("Vitesse", tag="clip_speed_row"):
                dpg.add_slider_int(tag="clip_speed", width=-1, format="1×", no_input=True,
                                   max_value=len(_SPEED_PRESETS) - 1,
                                   default_value=_SPEED_PRESETS.index(1.0),
                                   callback=_speed_changed, user_data=(None, _SPEED_PRESETS))
                with dpg.tooltip("clip_speed"):
                    dpg.add_text("Choisissez une vitesse prédéfinie.\n"
                                 "1× = normale. 2× divise la durée du clip par deux.\n"
                                 "L’image et le son changent de vitesse ensemble.")
            with _row("Durée clip", tag="clip_speed_duration_row"):
                dpg.add_text("", tag="clip_speed_duration")
            with _row("Durée (s)", tag="clip_image_duration_row"):
                dpg.add_input_float(tag="clip_image_duration", width=-1, step=0, format="%.2f",
                                    on_enter=True,
                                    callback=lambda s, v: _update(display_duration=v))
    _layer_section("layer", "clip_track")


def _layer_section(section, track):
    with _section(section, "Calque"), _rows():
        with _row("Piste"):
            dpg.add_input_int(tag=track, width=-1, step=0, min_value=1,
                              max_value=100, min_clamped=True, max_clamped=True,
                              on_enter=True, callback=lambda s, v: _update(track=v - 1))
            with dpg.tooltip(track):
                dpg.add_text("Les pistes plus hautes passent devant, quel que soit le type.")
        with _row("Ordre"), dpg.group(horizontal=True):
            dpg.add_button(label="Derrière", tag=f"{track}_back",
                           callback=lambda: _action("move_layer", -1))
            dpg.add_button(label="Devant", tag=f"{track}_front",
                           callback=lambda: _action("move_layer", 1))


def _audio_tab() -> None:
    with dpg.group(tag="clip_audio"):
        _animation_hint("audio")
        with _section("volume", "Volume", on_reset=lambda: _update(volume=1.0, muted=False)):
            with _rows():
                with _animated_row("Volume", "clip_volume"):
                    dpg.add_slider_float(tag="clip_volume", width=-1, min_value=0,
                                         max_value=200, format="%.0f %%",
                                         callback=_set_volume)
                with _row("Muet"):
                    dpg.add_checkbox(tag="clip_muted", callback=lambda s, v: _update(muted=v))


def _effects_tab() -> None:
    with dpg.group(tag="clip_effects"):
        dpg.add_text(_NO_EFFECT, tag="clip_effects_empty", wrap=0, color=COLORS["label_muted"])
        dpg.add_group(tag="clip_effects_list")


def _text_tab() -> None:
    with _section("text_content", "Contenu"):
        dpg.add_input_text(tag=TEXT_CONTENT, width=-1, height=86, multiline=True,
                           callback=_text_changed)
    with _section("text_style", "Style"), _rows():
        with _row("Police"):
            dpg.add_combo(list(FONTS), tag="clip_text_font", width=-1,
                          callback=lambda s, v: _action("update_text_style", font=FONTS[v]))
        with _row("Taille"):
            dpg.add_input_int(tag="clip_text_size", width=-1, min_value=12, max_value=200,
                              min_clamped=True, max_clamped=True, on_enter=True,
                              callback=lambda s, v: _action("update_text_style", size=v))
            with dpg.tooltip("clip_text_size"):
                dpg.add_text("Taille en pixels en Full HD, adaptée à la résolution de sortie.")
        with _row("Couleur"):
            dpg.add_color_edit(tag="clip_text_color", width=-1, no_alpha=True, no_inputs=True,
                               callback=_text_color_changed)
        with _row("Alignement"):
            dpg.add_combo(list(ALIGNMENTS), tag="clip_text_alignment", width=-1,
                          callback=lambda s, v: _action("update_text_style",
                                                        alignment=ALIGNMENTS[v]))
        with _row("Gras"):
            dpg.add_checkbox(tag="clip_text_bold",
                             callback=lambda s, v: _action("update_text_style", bold=v))
    with _section("text_box", "Zone de texte"):
        _animation_hint("text")
        with _rows():
            for field, label in _TEXT_BOX_FIELDS:
                with _animated_row(label, f"clip_text_{field}"):
                    dpg.add_input_float(tag=f"clip_text_{field}", width=-1, step=0,
                                        format="%.1f %%", on_enter=True, user_data=field,
                                        callback=_text_box_changed)
    with _section("text_timing", "Temps"), _rows():
        for field, label in (("timeline_start", "Début (s)"), ("display_duration", "Durée (s)")):
            with _row(label):
                dpg.add_input_float(tag=f"clip_text_{field}", width=-1, step=0, format="%.2f",
                                    on_enter=True, user_data=field,
                                    callback=lambda s, v, name: _update(**{name: v}))
    _layer_section("text_layer", "clip_text_track")


def _animation_hint(tab):
    dpg.add_text(_ANIMATION_HINT, tag=f"inspector_animation_hint_{tab}", show=False,
                 wrap=0, color=COLORS["label_muted"])


def _keyframes_tab() -> None:
    dpg.add_text("", tag="keyframe_cursor", wrap=0, color=COLORS["label_muted"])
    dpg.add_text("Placez la tête de lecture, puis cliquez sur ◇",
                 color=COLORS["label_muted"])
    dpg.add_text("pour poser une clé sur la propriété souhaitée.",
                 color=COLORS["label_muted"])
    dpg.add_spacer(height=3)
    with _section("kf_props", "Propriétés animées"), _rows():
        for name in GEOMETRY_PROPERTIES:
            with _row(PROPERTIES[name][0], tag=f"keyframe_row_{name}"):
                _key_button(name)
        with _row(PROPERTIES["volume"][0], tag="keyframe_row_volume"):
            _key_button("volume")
        with _row(PROPERTIES["opacity"][0], tag="keyframe_row_opacity"):
            _key_button("opacity")
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
            reset_tag = f"inspector_reset_{key}"
            dpg.add_image_button(inspector_icons.texture_tag(icon), tag=reset_tag,
                                 callback=lambda: None if _is_locked(reset_tag) else on_reset())
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


def _animated_field_tag(control):
    return f"inspector_animated_{control}"


@contextmanager
def _animated_row(label, control):
    with _row(label):
        yield
        # L'affichage non éditable ouvre la clé sans modifier la valeur.
        tag = _animated_field_tag(control)
        dpg.add_button(tag=tag, label="◆ Animé ›", width=-1, show=False,
                       callback=_open_animated_value, user_data=control)
        dpg.bind_item_theme(tag, ANIMATED_FIELD_THEME)
        with dpg.tooltip(tag):
            dpg.add_text("Ouvrir l’image clé qui pilote ce réglage.")


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
    with dpg.theme(tag=ANIMATED_FIELD_THEME), dpg.theme_component(dpg.mvButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (48, 50, 59, 255))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (65, 70, 88, 255))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (76, 83, 104, 255))
        dpg.add_theme_color(dpg.mvThemeCol_Text, (188, 191, 199, 255))
        dpg.add_theme_style(dpg.mvStyleVar_ButtonTextAlign, 0, 0.5)


# --- Synchronisation ------------------------------------------------------------

def bind(editor, on_error):
    global _editor, _on_error
    _editor, _on_error = editor, on_error
    refresh()


def refresh():
    clip = _editor.selected if _editor else None
    dpg.configure_item("clip_properties", show=clip is not None)
    dpg.configure_item("clip_subtitle", show=clip is not None)
    dpg.set_value("clip_name", clip.label if clip else _EMPTY)
    if clip is None:
        return
    _refresh_animation_locks(clip)
    is_text = isinstance(clip, TextClip)
    for tab in (TAB_VIDEO, TAB_EFFECTS):
        dpg.configure_item(tab, show=not is_text)
    dpg.configure_item(TAB_TEXT, show=is_text)
    text_tab_active = dpg.get_value(TABS) in (TAB_TEXT, dpg.get_alias_id(TAB_TEXT))
    if is_text:
        dpg.configure_item(TAB_AUDIO, show=False)
        if not text_tab_active and dpg.get_value(TABS) not in (
            TAB_KEYFRAMES, dpg.get_alias_id(TAB_KEYFRAMES),
        ):
            dpg.set_value(TABS, TAB_TEXT)
        _refresh_text(clip)
        _refresh_keyframes(clip)
        return
    if text_tab_active:
        dpg.set_value(TABS, TAB_VIDEO)
    is_image = isinstance(clip, ImageClip)
    dpg.set_value("clip_subtitle", _subtitle(clip))
    dpg.set_value("clip_track", clip.track + 1)
    dpg.set_value("clip_start", clip.timeline_start)
    for row in ("clip_in_row", "clip_out_row", "clip_speed_row", "clip_speed_duration_row"):
        dpg.configure_item(row, show=not is_image)
    dpg.configure_item("clip_image_duration_row", show=is_image)
    if is_image:
        dpg.set_value("clip_image_duration", clip.display_duration)
    else:
        dpg.set_value("clip_in", clip.source_start)
        dpg.set_value("clip_out", clip.source_end)
        _refresh_speed_slider(clip)
        minutes, seconds = divmod(round(clip.duration, 2), 60)
        duration = f"{int(minutes)} min {seconds:05.2f} s" if minutes else f"{seconds:.2f} s"
        dpg.set_value("clip_speed_duration", duration)
    dpg.configure_item("clip_geometry", show=clip.media.kind != MediaKind.AUDIO)
    _refresh_geometry(clip.transform)
    has_audio = clip.media.has_audio and not is_image
    dpg.configure_item(TAB_AUDIO, show=has_audio)
    if not has_audio and dpg.get_value(TABS) in (TAB_AUDIO, dpg.get_alias_id(TAB_AUDIO)):
        dpg.set_value(TABS, dpg.get_alias_id(TAB_VIDEO))
    dpg.set_value("clip_volume", clip.volume * 100)
    dpg.set_value("clip_muted", clip.muted)
    _refresh_effects(clip)
    _refresh_keyframes(clip)


def _refresh_speed_slider(clip):
    shown_clip, choices = dpg.get_item_user_data("clip_speed")
    if shown_clip != clip.id or clip.speed not in choices:
        # Une vitesse personnalisée d'un ancien projet reste disponible pour ce clip.
        choices = tuple(sorted({*_SPEED_PRESETS, clip.speed}))
        dpg.set_item_user_data("clip_speed", (clip.id, choices))
    label = f"{clip.speed:g}".replace(".", ",") + "×"
    dpg.configure_item("clip_speed", max_value=len(choices) - 1, format=label)
    index = choices.index(clip.speed)
    if dpg.get_value("clip_speed") != index:
        dpg.set_value("clip_speed", index)


def _speed_changed(sender, index, data):
    clip_id, choices = data
    clip = _selected()
    if clip is not None and clip.id == clip_id and 0 <= index < len(choices):
        _action("set_clip_speed", choices[index])


def _refresh_keyframes(clip):
    is_text = isinstance(clip, TextClip)
    for name in GEOMETRY_PROPERTIES:
        dpg.configure_item(f"keyframe_row_{name}",
                           show=is_text or clip.media.kind != MediaKind.AUDIO)
    dpg.configure_item("keyframe_row_volume", show=not is_text and clip.media.has_audio)
    dpg.configure_item("keyframe_row_opacity", show=is_text)
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


def _refresh_animation_locks(clip):
    animated = {key.property for key in clip.keyframes}
    for tag, properties in _ANIMATED_CONTROLS.items():
        locked = not animated.isdisjoint(properties)
        dpg.configure_item(tag, enabled=not locked)
        display = _animated_field_tag(tag)
        if dpg.does_item_exist(display):
            dpg.configure_item(tag, show=not locked)
            dpg.configure_item(display, show=locked)
    for tab, properties in (
        ("video", _GEOMETRY_KEYS), ("audio", {"volume"}), ("text", _GEOMETRY_KEYS),
    ):
        dpg.configure_item(f"inspector_animation_hint_{tab}",
                           show=bool(animated.intersection(properties)))


def _is_locked(tag):
    clip = _selected()
    properties = _ANIMATED_CONTROLS.get(tag, ())
    return clip is not None and any(key.property in properties for key in clip.keyframes)


def _open_animated_value(sender, app_data, control):
    clip = _selected()
    if clip is None:
        return
    keys = [key for key in clip.keyframes if key.property in _ANIMATED_CONTROLS[control]]
    if not keys:
        return
    visible = [key for key in keys if key.time <= clip.duration]
    candidates = visible or keys
    primary = [key for key in candidates if key.property == _PRIMARY_KEYS.get(control)]
    position = _editor.playback.current_time()
    local_time = position - clip.timeline_start
    key = min(primary or candidates, key=lambda k: (abs(k.time - local_time), k.time))
    if "kf_edit" in _collapsed:
        _toggle(None, None, "kf_edit")
    dpg.set_value(TABS, TAB_KEYFRAMES)
    _action("select_keyframe", clip.id, key.property, key.time)
    if dpg.is_viewport_ok():
        dpg.configure_item("keyframe_value", tracked=True)
        dpg.set_frame_callback(dpg.get_frame_count() + 4,
                               lambda: dpg.configure_item("keyframe_value", tracked=False))


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
    clip = _editor.selected if _editor else None
    if clip is None:
        return
    local_time = max(0, min(clip.duration, position - clip.timeline_start))
    key_time = _editor.keyframe_time()
    for name in clip.keyframe_properties:
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
    _sync_property_values(clip, position)


def _sync_property_values(clip, position):
    local_time = max(0, min(clip.duration, position - clip.timeline_start))
    if isinstance(clip, TextClip):
        box = clip.unzoomed_transform_at(local_time)
        rendered = (clip.transform_at(local_time)
                    if any(key.property == "zoom" for key in clip.keyframes) else box)
        for field, _ in _TEXT_BOX_FIELDS:
            tag = f"clip_text_{field}"
            geometry = rendered if field in ("width", "height") else box
            _sync_numeric(tag, getattr(geometry, field) * 100)
    else:
        transform = clip.transform_at(local_time)
        cx, cy = center_offset(transform)
        _sync_numeric("clip_zoom", transform.width * 100)
        _sync_numeric("clip_pos_x", cx * 100)
        _sync_numeric("clip_pos_y", cy * 100)
        _sync_numeric("clip_volume", clip.volume_at(local_time) * 100)
        for side, _ in _CROP_SIDES:
            _sync_numeric(f"clip_crop_{side}", getattr(transform, f"crop_{side}") * 100)


def _sync_numeric(tag, value):
    display = _animated_field_tag(tag)
    if dpg.is_item_shown(display):
        label = f"{value:.1f} %   ◆ Animé ›"
        if dpg.get_item_label(display) != label:
            dpg.configure_item(display, label=label)
    if not dpg.is_item_active(tag) and abs(dpg.get_value(tag) - value) > 1e-5:
        dpg.set_value(tag, value)


def _subtitle(clip) -> str:
    media = clip.media
    parts = [_KINDS.get(media.kind, "Média")]
    if media.width and media.height:
        parts.append(f"{media.width}×{media.height}")
    parts.append(f"{clip.duration:.1f} s")
    return "  ·  ".join(parts)


def _refresh_text(clip: TextClip) -> None:
    dpg.set_value("clip_subtitle", f"Texte  ·  {clip.duration:.1f} s")
    if dpg.get_value(TEXT_CONTENT) != clip.content:
        dpg.set_value(TEXT_CONTENT, clip.content)
    style = clip.style
    font_name = next(label for label, font in FONTS.items() if font == style.font)
    dpg.set_value("clip_text_font", font_name)
    dpg.set_value("clip_text_size", style.size)
    dpg.set_value("clip_text_color", (*style.color, 255))
    label = next(label for label, value in ALIGNMENTS.items() if value == style.alignment)
    dpg.set_value("clip_text_alignment", label)
    dpg.set_value("clip_text_bold", style.bold)
    box = clip.unzoomed_transform_at(_editor.keyframe_time(clip))
    for field, _ in _TEXT_BOX_FIELDS:
        dpg.set_value(f"clip_text_{field}", getattr(box, field) * 100)
    dpg.set_value("clip_text_track", clip.track + 1)
    dpg.set_value("clip_text_timeline_start", clip.timeline_start)
    dpg.set_value("clip_text_display_duration", clip.display_duration)


def _text_changed(sender, value):
    clip = _selected()
    if isinstance(clip, TextClip):
        content = value[:MAX_TEXT_LENGTH]
        if content != value:
            dpg.set_value(sender, content)
        if content != clip.content:
            _update(content=content)


def _text_color_changed(sender):
    color = tuple(round(c) for c in dpg.get_value(sender)[:3])
    _action("update_text_style", color=color)


def _text_box_changed(sender, value, field):
    clip = _selected()
    if isinstance(clip, TextClip) and not _is_locked(f"clip_text_{field}"):
        _action("set_animated_value", field, value / 100)


def _refresh_geometry(t) -> None:
    cx, cy = center_offset(t)
    dpg.set_value("clip_zoom", t.width * 100)
    dpg.set_value("clip_pos_x", cx * 100)
    dpg.set_value("clip_pos_y", cy * 100)
    dpg.set_value("clip_rotation", t.rotation)
    dpg.set_value("clip_flip_horizontal", t.flip_horizontal)
    dpg.set_value("clip_flip_vertical", t.flip_vertical)
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
    if _selected() is not None and not _is_locked("clip_zoom"):
        _action("set_animated_value", "zoom", percent / 100)


def _set_volume(sender, percent):
    if not _is_locked("clip_volume"):
        _update(volume=percent / 100)


def _set_position(x=None, y=None):
    clip = _selected()
    if clip is None:
        return
    if (x is not None and _is_locked("clip_pos_x")) or (y is not None and _is_locked("clip_pos_y")):
        return
    cx, cy = center_offset(clip.transform)
    cx = cx if x is None else x / 100
    cy = cy if y is None else y / 100
    # Régler un axe libre ne doit pas créer de clé sur l'autre axe.
    _transform(lambda: with_center_offset(clip.transform, cx, cy), animate=False)


def _bounds(clip, transform):
    return fitted_bounds(transform, clip.media.width, clip.media.height,
                         _editor.project.canvas_ratio)


def _crop_changed(sender, percent, side):
    clip = _selected()
    if clip is not None and not _is_locked(f"clip_crop_{side}"):
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


def _transform(build, *, animate=True):
    """Calcule la nouvelle géométrie ; une valeur hors bornes est signalée sans rien changer."""
    try:
        transform = build()
    except ValueError as exc:
        refresh()
        if _on_error:
            _on_error(str(exc))
        return
    _update(transform=transform, animate_transform=animate)


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
