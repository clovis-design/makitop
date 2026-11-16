"""Application des effets vidéo (modèle : makitop.model.effects) sur une image numpy."""

from dataclasses import dataclass

import cv2
import numpy as np

_LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_SEPIA = np.array([[0.393, 0.769, 0.189],
                   [0.349, 0.686, 0.168],
                   [0.272, 0.534, 0.131]], dtype=np.float32)


@dataclass(frozen=True)
class _Context:
    amount: float
    time: float       # secondes écoulées depuis le début du clip
    duration: float   # durée du clip
    seed: int         # numéro d'image : bruit et secousses reproductibles


def apply(image, effects, local_t=0.0, duration=1.0, frame_seed=0):
    """Applique les effets dans l'ordre sur une image uint8 RGB ou RGBA.

    Les fondus ajoutent un canal alpha : le calque laisse voir ceux du dessous."""
    if not effects:
        return image
    rgb = image[..., :3].astype(np.float32)
    alpha = image[..., 3].astype(np.float32) if image.shape[2] == 4 else None
    for effect in effects:
        ctx = _Context(float(effect.amount), float(local_t), max(float(duration), 1e-6),
                       int(frame_seed))
        rgb, alpha = _EFFECTS[effect.kind](rgb, alpha, ctx)
    rgb = np.rint(np.clip(rgb, 0, 255)).astype(np.uint8)
    if alpha is None:
        return rgb
    alpha = np.rint(np.clip(alpha, 0, 255)).astype(np.uint8)
    return np.dstack((rgb, alpha))


def _mix(original, processed, amount):
    return original + (processed - original) * amount


def _gray(rgb):
    return (rgb @ _LUMA)[..., None]


# ── Filtres couleur ──────────────────────────────────────────────────────────

def _bw(rgb, alpha, ctx):
    return _mix(rgb, np.repeat(_gray(rgb), 3, axis=2), ctx.amount), alpha


def _sepia(rgb, alpha, ctx):
    return _mix(rgb, rgb @ _SEPIA.T, ctx.amount), alpha


def _vintage(rgb, alpha, ctx):
    toned = (rgb @ _SEPIA.T) * 0.55 + rgb * 0.45
    faded = (toned - 128) * 0.8 + 128 + 12
    return _mix(rgb, faded, ctx.amount), alpha


def _cold(rgb, alpha, ctx):
    return rgb + ctx.amount * np.array([-20, 0, 30], dtype=np.float32), alpha


def _warm(rgb, alpha, ctx):
    return rgb + ctx.amount * np.array([30, 8, -25], dtype=np.float32), alpha


def _invert(rgb, alpha, ctx):
    return _mix(rgb, 255 - rgb, ctx.amount), alpha


# ── Réglages ─────────────────────────────────────────────────────────────────

def _brightness(rgb, alpha, ctx):
    return rgb + ctx.amount * 100, alpha


def _contrast(rgb, alpha, ctx):
    return (rgb - 128) * (1 + ctx.amount) + 128, alpha


def _saturation(rgb, alpha, ctx):
    gray = _gray(rgb)
    return gray + (rgb - gray) * (1 + ctx.amount), alpha


# ── Effets visuels ───────────────────────────────────────────────────────────

def _blur(rgb, alpha, ctx):
    sigma = ctx.amount * min(rgb.shape[:2]) * 0.02
    if sigma < 0.3:
        return rgb, alpha
    return cv2.GaussianBlur(rgb, (0, 0), sigma), alpha


def _vignette(rgb, alpha, ctx):
    h, w = rgb.shape[:2]
    y, x = np.ogrid[-1:1:complex(0, h), -1:1:complex(0, w)]
    radius = np.sqrt(x * x + y * y) / np.sqrt(2)
    mask = 1 - ctx.amount * np.clip((radius - 0.3) / 0.7, 0, 1) ** 1.5
    return rgb * mask[..., None].astype(np.float32), alpha


def _pixelate(rgb, alpha, ctx):
    h, w = rgb.shape[:2]
    if ctx.amount < 0.02:
        return rgb, alpha
    block = max(2, round(ctx.amount * min(h, w) / 10))
    small = (max(1, w // block), max(1, h // block))

    def pixels(channel):
        reduced = cv2.resize(channel, small, interpolation=cv2.INTER_AREA)
        return cv2.resize(reduced, (w, h), interpolation=cv2.INTER_NEAREST)
    return pixels(rgb), None if alpha is None else pixels(alpha)


def _glitch(rgb, alpha, ctx):
    shift = round(ctx.amount * rgb.shape[1] * 0.02)
    if shift < 1:
        return rgb, alpha
    out = rgb.copy()
    out[..., 0] = np.roll(rgb[..., 0], shift, axis=1)
    out[..., 2] = np.roll(rgb[..., 2], -shift, axis=1)
    return out, alpha


def _grain(rgb, alpha, ctx):
    noise = np.random.default_rng(ctx.seed).normal(0, ctx.amount * 40, rgb.shape[:2] + (1,))
    return rgb + noise.astype(np.float32), alpha


def _mirror(rgb, alpha, ctx):
    # Copies contiguës : OpenCV refuse les vues à pas négatif.
    flipped = np.ascontiguousarray(rgb[:, ::-1])
    return flipped, None if alpha is None else np.ascontiguousarray(alpha[:, ::-1])


# ── Effets animés ────────────────────────────────────────────────────────────

def _with_alpha(rgb, alpha, factor):
    if alpha is None:
        alpha = np.full(rgb.shape[:2], 255, dtype=np.float32)
    return rgb, alpha * factor


def _fade_in(rgb, alpha, ctx):
    return _with_alpha(rgb, alpha, min(1.0, max(0.0, ctx.time / ctx.amount)))


def _fade_out(rgb, alpha, ctx):
    return _with_alpha(rgb, alpha, min(1.0, max(0.0, (ctx.duration - ctx.time) / ctx.amount)))


def _warp(rgb, alpha, matrix):
    h, w = rgb.shape[:2]

    def warp(channel):
        return cv2.warpAffine(channel, matrix, (w, h), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REFLECT)
    return warp(rgb), None if alpha is None else warp(alpha)


def _zoom(rgb, alpha, ctx):
    scale = 1 + ctx.amount * min(1.0, max(0.0, ctx.time / ctx.duration))
    if scale <= 1:
        return rgb, alpha
    h, w = rgb.shape[:2]
    cx, cy = w / 2, h / 2
    matrix = np.float32([[scale, 0, (1 - scale) * cx], [0, scale, (1 - scale) * cy]])
    return _warp(rgb, alpha, matrix)


def _shake(rgb, alpha, ctx):
    amplitude = ctx.amount * min(rgb.shape[:2]) * 0.03
    if amplitude < 0.5:
        return rgb, alpha
    dx, dy = np.random.default_rng(ctx.seed + 1).uniform(-amplitude, amplitude, 2)
    return _warp(rgb, alpha, np.float32([[1, 0, dx], [0, 1, dy]]))


_EFFECTS = {
    "bw": _bw, "sepia": _sepia, "vintage": _vintage, "cold": _cold, "warm": _warm,
    "invert": _invert, "brightness": _brightness, "contrast": _contrast,
    "saturation": _saturation, "blur": _blur, "vignette": _vignette, "pixelate": _pixelate,
    "glitch": _glitch, "grain": _grain, "mirror": _mirror, "fade_in": _fade_in,
    "fade_out": _fade_out, "zoom": _zoom, "shake": _shake,
}
