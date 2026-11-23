"""Grille de vignettes commune aux catalogues du panneau médias."""

import dearpygui.dearpygui as dpg

THUMB_W, THUMB_H = 84, 47
COLUMNS = 3
TILE_THEME = "catalog_tile_theme"


def _load_theme() -> None:
    if dpg.does_alias_exist(TILE_THEME):
        return
    with dpg.theme(tag=TILE_THEME):
        with dpg.theme_component(dpg.mvImageButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (60, 120, 175, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (40, 100, 155, 255))
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 2, 2)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6)
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 2)


def section(title, kinds, add_tile) -> None:
    _load_theme()
    dpg.add_spacer(height=4)
    dpg.add_text(title)
    with dpg.table(header_row=False) as table:
        for _ in range(COLUMNS):
            dpg.add_table_column()
        for start in range(0, len(kinds), COLUMNS):
            with dpg.table_row():
                for kind in kinds[start:start + COLUMNS]:
                    add_tile(kind)
    dpg.bind_item_theme(table, TILE_THEME)


def tile(button, texture, label, description, callback, kind, *, enabled=True) -> None:
    with dpg.table_cell():
        dpg.add_image_button(texture, tag=button, width=THUMB_W, height=THUMB_H,
                             callback=callback, user_data=kind, enabled=enabled)
        with dpg.tooltip(button):
            dpg.add_text(description)
        dpg.add_text(label)
