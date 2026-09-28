"""Calcul de la taille des zones de la fenêtre principale (pur, sans Dear PyGui, donc testable)."""

from dataclasses import dataclass

MENU_BAR_HEIGHT = 20
SPACING = 8  # espace horizontal entre deux zones
V_SPACING = 4  # espace vertical entre deux zones (item_spacing par défaut de Dear PyGui)
SIDEBAR_WIDTH = 80
MEDIA_RATIO = 0.25
PROPERTIES_RATIO = 0.22
TIMELINE_RATIO = 0.4
MIN_PANEL = 50


@dataclass(frozen=True)
class Size:
    width: int
    height: int


@dataclass(frozen=True)
class Layout:
    sidebar: Size
    media: Size
    preview: Size
    properties: Size
    timeline: Size


def compute_layout(width: int, height: int) -> Layout:
    """Répartit la fenêtre.

    À gauche, sur toute la hauteur : la barre de navigation puis le panneau médias.
    À droite : preview et propriétés en haut, timeline en bas.
    """
    inner_w = max(width - 2 * SPACING, SIDEBAR_WIDTH + 3 * MIN_PANEL)
    inner_h = max(height - MENU_BAR_HEIGHT - 3 * SPACING, 2 * MIN_PANEL)

    media_w = max(int(inner_w * MEDIA_RATIO), MIN_PANEL)
    right_w = max(inner_w - SIDEBAR_WIDTH - media_w - 2 * SPACING, 2 * MIN_PANEL)
    properties_w = max(int(inner_w * PROPERTIES_RATIO), MIN_PANEL)
    preview_w = max(right_w - properties_w - SPACING, MIN_PANEL)

    timeline_h = max(int(inner_h * TIMELINE_RATIO), MIN_PANEL)
    top_h = max(inner_h - timeline_h, MIN_PANEL)
    full_h = top_h + V_SPACING + timeline_h

    return Layout(
        sidebar=Size(SIDEBAR_WIDTH, full_h),
        media=Size(media_w, full_h),
        preview=Size(preview_w, top_h),
        properties=Size(properties_w, top_h),
        timeline=Size(right_w, timeline_h),
    )
