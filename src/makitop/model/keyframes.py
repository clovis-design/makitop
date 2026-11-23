"""Images clés en secondes locales au clip, indépendantes de sa position et du FPS."""

import math
from dataclasses import dataclass
from itertools import pairwise

PROPERTIES = {
    "x": ("Position X", -8, 8),
    "y": ("Position Y", -8, 8),
    "zoom": ("Zoom", 0, 8),
    "width": ("Largeur", 0, 8),
    "height": ("Hauteur", 0, 8),
    "volume": ("Volume", 0, 2),
}
INTERPOLATIONS = {"Linéaire": "linear", "Douce": "smooth", "Constante": "constant"}


@dataclass(frozen=True)
class Keyframe:
    property: str
    time: float
    value: float
    # Interpolation du segment qui PART de cette image clé.
    interpolation: str = "linear"

    def __post_init__(self):
        if self.property not in PROPERTIES:
            raise ValueError("Propriété d'image clé inconnue.")
        if not math.isfinite(self.time) or self.time < 0:
            raise ValueError("Temps d'image clé invalide.")
        _, low, high = PROPERTIES[self.property]
        if (not math.isfinite(self.value) or not low <= self.value <= high
                or (self.property in ("zoom", "width", "height") and self.value <= 0)):
            raise ValueError("Valeur d'image clé invalide.")
        if self.interpolation not in INTERPOLATIONS.values():
            raise ValueError("Interpolation inconnue.")


def curve(keyframes, property):
    return sorted((k for k in keyframes if k.property == property), key=lambda k: k.time)


def interpolate(left, right, time):
    """Accepte un temps scalaire ou un tableau de temps compris dans le segment."""
    if left.interpolation == "constant":
        return left.value
    fraction = (time - left.time) / (right.time - left.time)
    if left.interpolation == "smooth":
        fraction = fraction * fraction * (3 - 2 * fraction)
    return left.value + (right.value - left.value) * fraction


def value_at(keyframes, property, time, default):
    points = curve(keyframes, property)
    if not points:
        return default
    if time <= points[0].time:
        return points[0].value
    for left, right in pairwise(points):
        if time < right.time:
            return interpolate(left, right, time)
    return points[-1].value


def upsert(keyframes, keyframe):
    """Une seule image clé par propriété et instant (tolérance aux arrondis)."""
    result = [k for k in keyframes if not (
        k.property == keyframe.property and abs(k.time - keyframe.time) < 1e-9
    )]
    return tuple(sorted([*result, keyframe], key=lambda k: (k.property, k.time)))
