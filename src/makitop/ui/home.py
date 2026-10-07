"""Page d'accueil : affichée au lancement à la place de l'éditeur. Elle propose de créer
ou d'ouvrir un projet et liste les projets connus, du plus récemment utilisé au plus ancien."""

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import dearpygui.dearpygui as dpg

from makitop.storage.recent import RecentProject
from makitop.ui.assets.style import COLORS, FONT_INTER

TAG = "home_window"
CONTENT_TAG = "home_content"
TITLE_TAG = "home_title"
NEW_BUTTON = "home_new_project"
OPEN_BUTTON = "home_open_project"
LIST_TAG = "home_project_list"

CONTENT_WIDTH = 820
_MUTED = (150, 155, 175)
_TITLE_FONT_SIZE = 36


def create(on_new: Callable[[], None], on_open: Callable[[], None]) -> None:
    """Crée la page (cachée). `set_projects` remplit la liste, ui/screens.py l'affiche."""
    with dpg.window(
        tag=TAG,
        show=False,
        no_title_bar=True,
        no_move=True,
        no_resize=True,
        no_scrollbar=True,
    ):
        dpg.add_spacer(height=30)
        with dpg.child_window(tag=CONTENT_TAG, width=CONTENT_WIDTH, border=False):
            dpg.add_text("Makitop", tag=TITLE_TAG)
            dpg.add_text("Logiciel de montage vidéo", color=_MUTED)
            dpg.add_spacer(height=16)
            with dpg.group(horizontal=True):
                dpg.add_button(
                    tag=NEW_BUTTON,
                    label="Nouveau projet",
                    width=200,
                    height=40,
                    callback=lambda *_: on_new(),
                )
                dpg.add_button(
                    tag=OPEN_BUTTON,
                    label="Ouvrir un projet...",
                    width=200,
                    height=40,
                    callback=lambda *_: on_open(),
                )
            dpg.add_spacer(height=24)
            dpg.add_text("Projets")
            dpg.add_separator()
            dpg.add_group(tag=LIST_TAG)
    _apply_style()
    set_projects([], lambda path: None)


def set_projects(projects: list[RecentProject], on_select: Callable[[Path], None]) -> None:
    """Remplace la liste ; `projects` est déjà trié du plus récent au plus ancien."""
    dpg.delete_item(LIST_TAG, children_only=True)
    if not projects:
        dpg.add_text(
            "Aucun projet pour l'instant. Crée un nouveau projet ou ouvre un fichier .makitop.",
            parent=LIST_TAG,
            color=_MUTED,
        )
        return
    now = datetime.now()
    with dpg.table(
        parent=LIST_TAG,
        header_row=True,
        scrollY=True,
        row_background=True,
        borders_innerH=True,
        policy=dpg.mvTable_SizingStretchProp,
        height=-1,
    ):
        dpg.add_table_column(label="Nom", init_width_or_weight=3)
        dpg.add_table_column(label="Dossier", init_width_or_weight=5)
        dpg.add_table_column(label="Dernière utilisation", init_width_or_weight=3)
        for project in projects:
            with dpg.table_row():
                dpg.add_selectable(
                    label=project.name,
                    span_columns=True,
                    callback=lambda *_, p=project.path: on_select(p),
                )
                dpg.add_text(str(project.path.parent), color=_MUTED)
                dpg.add_text(format_last_used(project.last_used, now), color=_MUTED)


def resize(width: int, height: int) -> None:
    """Centre le contenu dans la fenêtre."""
    dpg.set_item_pos(CONTENT_TAG, [max((width - CONTENT_WIDTH) // 2, 16), 40])
    dpg.configure_item(CONTENT_TAG, height=max(height - 60, 200))


def format_last_used(when: datetime | None, now: datetime) -> str:
    if when is None:
        return "—"
    days = (now.date() - when.date()).days
    if days <= 0:
        return f"Aujourd'hui à {when:%H:%M}"
    if days == 1:
        return f"Hier à {when:%H:%M}"
    if days < 7:
        return f"Il y a {days} jours"
    return f"{when:%d/%m/%Y}"


def _apply_style() -> None:
    with dpg.theme() as theme, dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLORS["bg_panel"])
        dpg.add_theme_color(dpg.mvThemeCol_ChildBg, COLORS["bg_panel"])
        dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text_main"])
        dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)
    dpg.bind_item_theme(TAG, theme)

    if os.path.exists(FONT_INTER):
        with dpg.font_registry():
            title_font = dpg.add_font(FONT_INTER, _TITLE_FONT_SIZE)
        dpg.bind_item_font(TITLE_TAG, title_font)
