"""Catalogue des effets vidéo applicables à un clip, indépendant du moteur de rendu."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class EffectSpec:
    label: str
    category: str
    min: float
    max: float
    default: float
    unit: str = ""
    description: str = ""

    @property
    def adjustable(self) -> bool:
        return self.max > self.min


FILTERS, ADJUSTMENTS, VISUALS, ANIMATED = "Filtres", "Réglages", "Effets visuels", "Animés"
CATEGORIES = (FILTERS, ADJUSTMENTS, VISUALS, ANIMATED)

CATALOG: dict[str, EffectSpec] = {
    "bw": EffectSpec("Noir & blanc", FILTERS, 0, 1, 1, "%", "Retire les couleurs."),
    "sepia": EffectSpec("Sépia", FILTERS, 0, 1, 1, "%", "Teinte brune des vieilles photos."),
    "vintage": EffectSpec("Vintage", FILTERS, 0, 1, 1, "%", "Couleurs passées et contraste doux."),
    "cold": EffectSpec("Froid", FILTERS, 0, 1, 1, "%", "Tire les couleurs vers le bleu."),
    "warm": EffectSpec("Chaud", FILTERS, 0, 1, 1, "%", "Tire les couleurs vers l'orange."),
    "invert": EffectSpec("Négatif", FILTERS, 0, 1, 1, "%", "Inverse les couleurs."),
    "brightness": EffectSpec("Luminosité", ADJUSTMENTS, -1, 1, 0.3, "%", "Éclaircit ou assombrit."),
    "contrast": EffectSpec("Contraste", ADJUSTMENTS, -1, 1, 0.3, "%", "Renforce ou adoucit le contraste."),
    "saturation": EffectSpec("Saturation", ADJUSTMENTS, -1, 1, 0.3, "%", "Couleurs plus vives ou plus ternes."),
    "blur": EffectSpec("Flou", VISUALS, 0, 1, 0.5, "%", "Flou gaussien."),
    "vignette": EffectSpec("Vignette", VISUALS, 0, 1, 0.5, "%", "Assombrit les bords."),
    "pixelate": EffectSpec("Pixelisation", VISUALS, 0, 1, 0.5, "%", "Gros pixels."),
    "glitch": EffectSpec("Glitch RGB", VISUALS, 0, 1, 0.5, "%", "Décale les canaux rouge et bleu."),
    "grain": EffectSpec("Grain", VISUALS, 0, 1, 0.5, "%", "Bruit de pellicule."),
    "mirror": EffectSpec("Miroir", VISUALS, 1, 1, 1, "", "Retourne l'image horizontalement."),
    "fade_in": EffectSpec("Fondu entrant", ANIMATED, 0.1, 5, 1, "s", "Apparition progressive."),
    "fade_out": EffectSpec("Fondu sortant", ANIMATED, 0.1, 5, 1, "s", "Disparition progressive."),
    "zoom": EffectSpec("Zoom progressif", ANIMATED, 0, 1, 0.3, "%", "Zoom lent pendant le clip."),
    "shake": EffectSpec("Tremblement", ANIMATED, 0, 1, 0.5, "%", "Secousses de caméra."),
}

# Effets dont le rendu change d'une image à l'autre, même sur une image fixe.
TIME_DEPENDENT = frozenset({"fade_in", "fade_out", "zoom", "shake", "grain"})


@dataclass(frozen=True)
class Effect:
    kind: str
    amount: float

    def __post_init__(self):
        spec = CATALOG.get(self.kind)
        if spec is None:
            raise ValueError(f"Effet inconnu : {self.kind!r}")
        if not isinstance(self.amount, (int, float)) or not math.isfinite(self.amount):
            raise ValueError("Valeur d'effet invalide.")
        if not spec.min - 1e-9 <= self.amount <= spec.max + 1e-9:
            raise ValueError(f"{spec.label} : valeur hors limites.")

    @property
    def spec(self) -> EffectSpec:
        return CATALOG[self.kind]
