"""Zone « Timeline » : pistes et clips (Dear PyGui Plot)."""

import dearpygui.dearpygui as dpg

TAG = "timeline_panel"
CURSOR = "timeline_cursor"
CLIPS = "timeline_clips"
IN = "timeline_source_in"
OUT = "timeline_source_out"
SELECTION = "timeline_selection"


def create() -> None:
    with dpg.child_window(tag=TAG, border=True):
        dpg.add_text("Timeline")
        dpg.add_separator()
        dpg.add_text("Sélectionnez une vidéo dans les médias, puis ajoutez une portion.")
        dpg.add_text("Aucune vidéo sélectionnée", tag=SELECTION)
        with dpg.group(horizontal=True):
            dpg.add_input_float(label="Entrée (s)", tag=IN, default_value=0, width=100)
            dpg.add_input_float(label="Sortie (s)", tag=OUT, default_value=0, width=100)
            dpg.add_button(label="Ajouter la portion", tag="timeline_add")
            dpg.add_button(label="Voir le montage", tag="timeline_show")
        dpg.add_slider_float(label="Position montage (s)", tag=CURSOR,
                             min_value=0, max_value=0, format="%.3f")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Couper au curseur", tag="timeline_split")
            dpg.add_button(label="Supprimer le clip sélectionné", tag="timeline_remove")
        dpg.add_listbox([], tag=CLIPS, num_items=3, width=-1)


def bind(on_add, on_show, on_seek, on_split, on_remove):
    dpg.set_item_callback("timeline_add", lambda: on_add(dpg.get_value(IN), dpg.get_value(OUT)))
    dpg.set_item_callback("timeline_show", lambda: on_show())
    dpg.set_item_callback(CURSOR, lambda _, value: on_seek(value))
    dpg.set_item_callback("timeline_split", on_split)
    dpg.set_item_callback("timeline_remove", on_remove)


def select_media(media):
    dpg.set_value(SELECTION, media.name)
    dpg.set_value(IN, 0.0)
    dpg.set_value(OUT, media.duration or 0.0)


def refresh(project):
    names = {m.id: m.name for m in project.media}
    labels = [
        f"{i + 1}. {names.get(c.media_id, '?')} | "
        f"montage {c.timeline_start:.3f}–{c.end:.3f} s | "
        f"source {c.source_in:.3f}–{c.source_out:.3f} s"
        for i, c in enumerate(project.timeline.clips)
    ]
    dpg.configure_item(CLIPS, items=labels)
    dpg.set_value(CLIPS, labels[0] if labels else "")
    dpg.configure_item(CURSOR, max_value=project.timeline.duration)


def selected_index():
    value = dpg.get_value(CLIPS)
    return int(value.split(".", 1)[0]) - 1 if value else None


def update_time(position):
    dpg.set_value(CURSOR, position)
