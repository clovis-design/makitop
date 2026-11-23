"""Styles et préréglages des zones de texte."""

from dataclasses import dataclass

from makitop.model.composition import Transform

ALIGNMENTS = {"Gauche": "left", "Centre": "center", "Droite": "right"}
FONTS = {
    "Inter": "inter",
    "DejaVu Serif": "serif",
    "DejaVu Serif italique": "serif_italic",
    "DejaVu Sans Mono": "mono",
}
MAX_TEXT_LENGTH = 2000


@dataclass(frozen=True)
class TextStyle:
    size: int = 64  # pixels pour un petit côté de 1080 px
    color: tuple[int, int, int] = (255, 255, 255)
    alignment: str = "center"
    bold: bool = False
    font: str = "inter"

    def __post_init__(self):
        if type(self.size) is not int or not 12 <= self.size <= 200:
            raise ValueError("La taille du texte doit être comprise entre 12 et 200 px.")
        if (not isinstance(self.color, tuple) or len(self.color) != 3
                or any(type(c) is not int or not 0 <= c <= 255 for c in self.color)):
            raise ValueError("Couleur de texte invalide.")
        if self.alignment not in ALIGNMENTS.values() or type(self.bold) is not bool:
            raise ValueError("Style de texte invalide.")
        if self.font not in FONTS.values():
            raise ValueError("Police de texte inconnue.")


@dataclass(frozen=True)
class TextPreset:
    label: str
    description: str
    content: str
    style: TextStyle
    box: Transform


PRESETS = {
    "title": TextPreset("Titre", "Un titre large et centré.", "Votre titre",
                        TextStyle(size=108, bold=True),
                        Transform(x=0.1, y=0.30, width=0.8, height=0.4)),
    "subtitle": TextPreset("Sous-titre", "Une ligne discrète en bas de l’image.",
                           "Votre sous-titre", TextStyle(size=52),
                           Transform(x=0.1, y=0.78, width=0.8, height=0.16)),
    "paragraph": TextPreset("Paragraphe", "Un bloc aligné à gauche, sur plusieurs lignes.",
                            "Écrivez votre texte ici.\nAjoutez autant de lignes que nécessaire.",
                            TextStyle(size=54, alignment="left"),
                            Transform(x=0.1, y=0.23, width=0.8, height=0.54)),
    "heading": TextPreset("Intertitre", "Un titre court pour séparer deux sections.",
                          "Nouvelle section", TextStyle(size=84, bold=True),
                          Transform(x=0.08, y=0.32, width=0.84, height=0.36)),
    "quote": TextPreset("Citation", "Une citation centrée avec des guillemets.",
                        "« Votre citation ici »\n— Auteur",
                        TextStyle(size=68, color=(235, 224, 255)),
                        Transform(x=0.1, y=0.22, width=0.8, height=0.56)),
    "caption": TextPreset("Légende", "Un repère discret, en bas à droite.",
                           "Lieu · Date", TextStyle(size=42, alignment="right"),
                           Transform(x=0.08, y=0.84, width=0.84, height=0.10)),
    "lower_third": TextPreset("Cartouche", "Présente une personne en bas à gauche.",
                              "Prénom Nom\nFonction",
                              TextStyle(size=58, bold=True, alignment="left"),
                              Transform(x=0.06, y=0.70, width=0.88, height=0.25)),
    "chapter": TextPreset("Chapitre", "Un repère numéroté pour introduire une partie.",
                           "CHAPITRE 01\nNom du chapitre",
                           TextStyle(size=76, color=(184, 214, 255), bold=True),
                           Transform(x=0.08, y=0.24, width=0.84, height=0.52)),
    "credits": TextPreset("Générique", "Un bloc centré pour les crédits de fin.",
                           "Réalisation\nVotre nom\n\nMerci d’avoir regardé",
                            TextStyle(size=48),
                            Transform(x=0.10, y=0.12, width=0.80, height=0.76)),
    "editorial": TextPreset("Éditorial", "Un titre à empattements, façon couverture de magazine.",
                            "À la une", TextStyle(size=110, bold=True, font="serif"),
                            Transform(x=0.08, y=0.28, width=0.84, height=0.44)),
    "elegant": TextPreset("Élégant", "Un titre en italique pour une introduction soignée.",
                          "Un moment à part",
                          TextStyle(size=84, color=(255, 227, 191), font="serif_italic"),
                          Transform(x=0.10, y=0.28, width=0.80, height=0.44)),
    "terminal": TextPreset("Terminal", "Un texte à chasse fixe, inspiré d’une console.",
                           "> SYSTÈME PRÊT\n> En attente",
                           TextStyle(size=56, color=(176, 245, 201), alignment="left",
                                     font="mono"),
                           Transform(x=0.08, y=0.62, width=0.84, height=0.32)),
}
