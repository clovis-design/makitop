"""Calcul de la taille des zones de la fenêtre principale (pur, sans Dear PyGui, donc testable)."""

from dataclasses import dataclass

MENU_BAR_HEIGHT = 20
SPACING = 8
SIDE_RATIO = 0.22
TIMELINE_RATIO = 0.35
MIN_PANEL = 50


@dataclass(frozen=True)
class Size:
    width: int
    height: int


@dataclass(frozen=True)
class Layout:
    media: Size
    preview: Size
    properties: Size
    timeline: Size


def compute_layout(width: int, height: int) -> Layout:
    """Répartit la fenêtre : 3 colonnes en haut (médias, preview, propriétés), timeline en bas."""
    inner_w = max(width - 2 * SPACING, 3 * MIN_PANEL)
    inner_h = max(height - MENU_BAR_HEIGHT - 3 * SPACING, 2 * MIN_PANEL)

    timeline_h = max(int(inner_h * TIMELINE_RATIO), MIN_PANEL)
    top_h = max(inner_h - timeline_h, MIN_PANEL)

    side_w = max(int(inner_w * SIDE_RATIO), MIN_PANEL)
    preview_w = max(inner_w - 2 * side_w - 2 * SPACING, MIN_PANEL)

    return Layout(
        media=Size(side_w, top_h),
        preview=Size(preview_w, top_h),
        properties=Size(side_w, top_h),
        timeline=Size(inner_w, timeline_h),
    )
