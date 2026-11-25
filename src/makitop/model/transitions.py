"""Catalogue des préréglages xfade et règles de placement dans le montage."""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from makitop.model.timeline import BaseClip

# Identifiants des préréglages documentés par FFmpeg ; « custom » n'est pas un preset.
GROUPS = {
    "Fondus": {
        "fade": "Fondu enchaîné", "fadeblack": "Fondu au noir",
        "fadewhite": "Fondu au blanc", "fadegrays": "Fondu en gris",
        "fadefast": "Fondu rapide", "fadeslow": "Fondu lent", "dissolve": "Dissolution",
    },
    "Balayages": {
        "wipeleft": "Vers la gauche", "wiperight": "Vers la droite", "wipeup": "Vers le haut",
        "wipedown": "Vers le bas", "smoothleft": "Doux ←", "smoothright": "Doux →",
        "smoothup": "Doux ↑", "smoothdown": "Doux ↓", "wipetl": "Coin haut gauche",
        "wipetr": "Coin haut droit", "wipebl": "Coin bas gauche", "wipebr": "Coin bas droit",
    },
    "Glissements": {
        "slideleft": "Poussée ←", "slideright": "Poussée →", "slideup": "Poussée ↑",
        "slidedown": "Poussée ↓", "coverleft": "Couverture ←", "coverright": "Couverture →",
        "coverup": "Couverture ↑", "coverdown": "Couverture ↓", "revealleft": "Révélation ←",
        "revealright": "Révélation →", "revealup": "Révélation ↑", "revealdown": "Révélation ↓",
    },
    "Formes et ouvertures": {
        "circlecrop": "Cercle", "rectcrop": "Rectangle", "distance": "Par distance",
        "radial": "Radial", "circleopen": "Iris : ouverture", "circleclose": "Iris : fermeture",
        "vertopen": "Ouverture verticale", "vertclose": "Fermeture verticale",
        "horzopen": "Ouverture horizontale", "horzclose": "Fermeture horizontale",
    },
    "Diagonales et bandes": {
        "diagtl": "Diag. haut gauche", "diagtr": "Diag. haut droit",
        "diagbl": "Diag. bas gauche", "diagbr": "Diag. bas droit",
        "hlslice": "Bandes ←", "hrslice": "Bandes →", "vuslice": "Bandes ↑",
        "vdslice": "Bandes ↓", "hlwind": "Vent ←", "hrwind": "Vent →",
        "vuwind": "Vent ↑", "vdwind": "Vent ↓",
    },
    "Effets de transition": {
        "pixelize": "Pixellisation", "hblur": "Flou horizontal",
        "squeezeh": "Compression horiz.", "squeezev": "Compression vert.",
        "zoomin": "Zoom entrant",
    },
}
CATALOG = {kind: label for group in GROUPS.values() for kind, label in group.items()}
MIN_DURATION, MAX_DURATION = 0.05, 5.0


@dataclass(frozen=True)
class Transition:
    outgoing_id: str
    incoming_id: str
    kind: str
    duration: float = 0.8

    def __post_init__(self):
        if (not isinstance(self.outgoing_id, str) or not isinstance(self.incoming_id, str)
                or self.outgoing_id == self.incoming_id
                or not self.outgoing_id or not self.incoming_id):
            raise ValueError("Une transition doit relier deux clips différents.")
        if self.kind not in CATALOG:
            raise ValueError("Transition inconnue.")
        if (type(self.duration) not in (int, float)
                or not MIN_DURATION <= self.duration <= MAX_DURATION):
            raise ValueError("La durée d’une transition doit être comprise entre 0,05 et 5 s.")


@dataclass(frozen=True)
class TransitionSpan:
    transition: Transition
    outgoing: "BaseClip"
    incoming: "BaseClip"
    start: float
    end: float
    suppress_until: float

    def progress(self, time):
        return (time - self.start) / (self.end - self.start)


def span_for(transition, outgoing, incoming, gap_tolerance=1e-8):
    """Centrer sur une coupe franche, ou démarrer au début d'un chevauchement."""
    cut = incoming.timeline_start
    gap = cut - outgoing.timeline_end
    if outgoing.timeline_start >= cut - 1e-8 or gap > gap_tolerance + 1e-8:
        return None
    overlap = min(outgoing.timeline_end, incoming.timeline_end) - cut
    if overlap > 1e-8:
        end = cut + min(overlap, transition.duration)
        return TransitionSpan(transition, outgoing, incoming, cut, end, cut + overlap)
    half = min(transition.duration / 2, cut - outgoing.timeline_start, incoming.duration)
    if not math.isfinite(half) or half <= 1e-8 or half < gap:
        return None
    return TransitionSpan(transition, outgoing, incoming, cut - half, cut + half, cut + half)
