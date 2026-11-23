"""Section « Effets » du panneau médias : catalogue de vignettes à appliquer au clip choisi."""

from collections.abc import Callable

import cv2
import dearpygui.dearpygui as dpg
import numpy as np

from makitop.engine.effects import video
from makitop.model.effects import CATALOG, CATEGORIES, Effect
from makitop.ui.panels import catalog_grid
from makitop.ui.panels.catalog_grid import THUMB_H, THUMB_W

REGISTRY = "effects_texture_registry"
HINT = "Sélectionnez un clip dans la timeline, puis cliquez sur un effet."
_HINT_COLOR = (150, 155, 175)
_TILE_BG = np.array([24, 28, 58], dtype=np.float32)
# Instant montré sur la vignette (clip de 2 s) pour que l'effet animé soit visible.
_PREVIEW_TIMES = {"fade_in": 0.4, "fade_out": 1.6, "zoom": 2.0}
_PREVIEW_SCALE = 4

_on_apply: Callable[[str], None] | None = None


def button_tag(kind: str) -> str:
    return f"effect_button_{kind}"


def texture_tag(kind: str) -> str:
    return f"effect_texture_{kind}"


def bind(on_apply: Callable[[str], None]) -> None:
    global _on_apply
    _on_apply = on_apply


def _sample(width: int, height: int) -> np.ndarray:
    """Paysage synthétique : ciel, soleil, collines."""
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None, None]
    x = np.linspace(0, 1, width, dtype=np.float32)[None, :, None]
    top, bottom = np.float32([70, 130, 220]), np.float32([250, 180, 120])
    image = np.broadcast_to(top * (1 - y) + bottom * y, (height, width, 3)).copy()
    sun = (x - 0.7) ** 2 * (width / height) ** 2 + (y - 0.42) ** 2 < 0.18 ** 2
    image[sun[..., 0]] = (255, 230, 120)
    hills = y > 0.72 + 0.06 * np.sin(x * 9)
    image[hills[..., 0]] = (40, 110, 70)
    return image.astype(np.uint8)


def thumbnail(kind: str) -> np.ndarray:
    """Vignette RGBA flottante (aplatie) montrant l'effet sur l'image d'exemple.

    L'effet est calculé à une taille proche de la preview, puis réduit, pour que
    la vignette ressemble au résultat réel (flou, pixels…)."""
    effect = Effect(kind, CATALOG[kind].default)
    large = _sample(THUMB_W * _PREVIEW_SCALE, THUMB_H * _PREVIEW_SCALE)
    image = video.apply(large, (effect,), _PREVIEW_TIMES.get(kind, 1.0), 2.0, 7)
    image = cv2.resize(image, (THUMB_W, THUMB_H), interpolation=cv2.INTER_AREA)
    rgb = image[..., :3].astype(np.float32)
    if image.shape[2] == 4:
        alpha = image[..., 3:4].astype(np.float32) / 255
        rgb = rgb * alpha + _TILE_BG * (1 - alpha)
    rgba = np.dstack((rgb / 255, np.ones(rgb.shape[:2], dtype=np.float32)))
    return rgba.astype(np.float32).ravel()


def _load_textures() -> None:
    if dpg.does_alias_exist(REGISTRY):
        return
    with dpg.texture_registry(tag=REGISTRY):
        for kind in CATALOG:
            dpg.add_static_texture(width=THUMB_W, height=THUMB_H,
                                   default_value=thumbnail(kind), tag=texture_tag(kind))


def build() -> None:
    """Construit le contenu de la section, dans le conteneur courant."""
    _load_textures()
    dpg.add_text(HINT, wrap=0, color=_HINT_COLOR)
    for category in CATEGORIES:
        kinds = [kind for kind, spec in CATALOG.items() if spec.category == category]
        catalog_grid.section(category, kinds, _tile)


def _tile(kind: str) -> None:
    spec = CATALOG[kind]
    catalog_grid.tile(button_tag(kind), texture_tag(kind), spec.label, spec.description,
                      _clicked, kind)


def _clicked(sender, app_data, kind: str) -> None:
    if _on_apply is not None:
        _on_apply(kind)
