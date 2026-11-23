"""Rendu des zones de texte, commun au lecteur et à l'export."""

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_FONT_DIR = Path(__file__).resolve().parents[1] / "ui" / "assets" / "fonts"
_FONT_FILES = {
    "inter": ("Inter-VariableFont_slnt,wght.ttf", "Inter-VariableFont_slnt,wght.ttf"),
    "serif": ("DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf"),
    "serif_italic": ("DejaVuSerif-Italic.ttf", "DejaVuSerif-BoldItalic.ttf"),
    "mono": ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf"),
}


@lru_cache(maxsize=48)
def load_font(family, size, bold):
    try:
        font = ImageFont.truetype(_FONT_DIR / _FONT_FILES[family][int(bold)], size)
        if family == "inter" and bold:
            axes = font.get_variation_axes()
            font.set_variation_by_axes([
                700 if axis["name"] == b"Weight" else axis["default"] for axis in axes
            ])
        return font
    except OSError:
        return ImageFont.load_default(size=size)


def _wrap(content, font, width):
    for paragraph in content.split("\n"):
        line = ""
        for word in paragraph.split():
            combined = f"{line} {word}" if line else word
            if font.getlength(combined) <= width:
                line = combined
                continue
            if line:
                yield line
            line = ""
            for char in word:
                if line and font.getlength(line + char) > width:
                    yield line
                    line = ""
                line += char
        yield line


def composite(canvas, content, style, box, *, opacity=1.0, font_scale=1.0):
    """Dessine le texte dans sa zone, sans allouer de pixels hors du cadre visible."""
    if opacity <= 0 or not content.strip():
        return
    height, width = canvas.shape[:2]
    x, y = round(box.x * width), round(box.y * height)
    box_w = max(1, round(box.width * width))
    box_h = max(1, round(box.height * height))
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + box_w, width), min(y + box_h, height)
    if x0 >= x1 or y0 >= y1:
        return

    scale = min(width, height) / 1080
    # Limite le travail de rasterisation pour les zooms très au-delà du cadre.
    size = max(1, min(max(width, height), round(style.size * scale * font_scale)))
    font = load_font(style.font, size, style.bold)
    stroke = max(1, round(scale))
    padding = min(stroke + 1, (box_w - 1) // 2)
    lines = list(_wrap(content, font, box_w - padding * 2))
    ascent, descent = font.getmetrics()
    line_height = ascent + descent + max(1, font.size // 8)
    start_y = max(0, (box_h - len(lines) * line_height) // 2)

    layer = Image.new("RGBA", (x1 - x0, y1 - y0))
    draw = ImageDraw.Draw(layer)
    for index, line in enumerate(lines):
        baseline = y - y0 + start_y + index * line_height + ascent
        if baseline - ascent >= layer.height:
            break
        if baseline + descent < 0:
            continue
        if style.alignment == "center":
            offset = (box_w - font.getlength(line)) / 2
        elif style.alignment == "right":
            offset = box_w - padding - font.getlength(line)
        else:
            offset = padding
        draw.text((x - x0 + offset, baseline), line, font=font, anchor="ls",
                  fill=(*style.color, 255), stroke_width=stroke, stroke_fill=(0, 0, 0, 200))

    if opacity < 1:
        layer.putalpha(layer.getchannel("A").point(lambda alpha: round(alpha * opacity)))
    target = canvas[y0:y1, x0:x1]
    target[:] = np.asarray(Image.alpha_composite(
        Image.fromarray(target).convert("RGBA"), layer,
    ).convert("RGB"))
