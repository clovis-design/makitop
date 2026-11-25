"""Curseurs natifs pour le backend GLFW de Dear PyGui sous Linux."""

import ctypes as ct
import math
import sys

from dearpygui import _dearpygui
from PIL import Image, ImageDraw

_SIZE = 33
_HOTSPOT = _SIZE // 2
_NO_MOUSE_CURSOR_CHANGE = 1 << 5  # ImGuiConfigFlags_NoMouseCursorChange
_ARROWS = (
    ((-8, 0), (8, 0)),
    ((-4, -4), (-8, 0), (-4, 4)),
    ((4, -4), (8, 0), (4, 4)),
)
_ROTATION = (
    tuple((7 * math.cos(a * math.pi / 12), 7 * math.sin(a * math.pi / 12))
          for a in range(2, 23)),
    ((1, -3), (6, -3.5), (6, -8)),
)
_SEEK = (((-8, 3), (8, 3)), ((0, -6), (0, 8)), ((-3, -6), (0, -2), (3, -6), (-3, -6)))


class _GLFWImage(ct.Structure):
    _fields_ = [("width", ct.c_int), ("height", ct.c_int), ("pixels", ct.POINTER(ct.c_ubyte))]


def _paths(kind, angle):
    if kind == "rotate":
        return _ROTATION
    if kind == "seek":
        return _SEEK
    if kind == "move":
        return (*_ARROWS, *(tuple((-y, x) for x, y in path) for path in _ARROWS))
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return tuple(tuple((x * c - y * s, x * s + y * c) for x, y in path) for path in _ARROWS)


def _pixels(kind, angle):
    scale = 4
    side = _SIZE * scale
    image = Image.new("RGBA", (side, side))
    draw = ImageDraw.Draw(image)
    # Un vrai curseur, plus lisible sur une image claire ou sur un écran HiDPI.
    factor = 1.5
    paths = [
        [((x * factor + _HOTSPOT + 0.5) * scale, (y * factor + _HOTSPOT + 0.5) * scale)
         for x, y in path]
        for path in _paths(kind, angle)
    ]
    fill = (255, 193, 82, 255) if kind == "crop" else (248, 250, 255, 255)
    for color, width in (((12, 16, 24, 255), 4), (fill, 2)):
        for path in paths:
            draw.line(path, fill=color, width=width * scale, joint="curve")
    return image.resize((_SIZE, _SIZE), Image.Resampling.LANCZOS).tobytes()


class NativeCursor:
    def __init__(self, glfw, config_flags):
        self._glfw = glfw
        self._config_flags = config_flags
        self._release_flag = False
        self._handles = {}
        self._window = None
        self._active_handle = None

    @classmethod
    def load(cls):
        if not sys.platform.startswith("linux"):
            return None
        # Réutiliser le GLFW de Dear PyGui : une autre instance n'a pas son GLFWwindow.
        try:
            glfw = ct.CDLL(_dearpygui.__file__)
            glfw.glfwGetCurrentContext.argtypes = []
            glfw.glfwGetCurrentContext.restype = ct.c_void_p
            glfw.glfwCreateCursor.argtypes = [ct.POINTER(_GLFWImage), ct.c_int, ct.c_int]
            glfw.glfwCreateCursor.restype = ct.c_void_p
            glfw.glfwSetCursor.argtypes = [ct.c_void_p, ct.c_void_p]
            glfw.glfwSetCursor.restype = None
            glfw.glfwDestroyCursor.argtypes = [ct.c_void_p]
            glfw.glfwDestroyCursor.restype = None
            # Dear PyGui n'expose pas ce réglage. Sur l'ABI ImGui 1.92 vérifiée,
            # ConfigFlags (int) est le premier champ de la structure ImGuiIO.
            version = glfw._ZN5ImGui10GetVersionEv
            version.argtypes = []
            version.restype = ct.c_char_p
            if not version().startswith(b"1.92."):
                return None
            current = glfw._ZN5ImGui17GetCurrentContextEv
            current.argtypes = []
            current.restype = ct.c_void_p
            if not current():
                return None
            get_io = glfw._ZN5ImGui5GetIOEv
            get_io.argtypes = []
            get_io.restype = ct.POINTER(ct.c_int)
            flags = get_io().contents
        except (AttributeError, OSError):
            return None
        return cls(glfw, flags)

    def apply(self, cue):
        window = self._glfw.glfwGetCurrentContext()
        if not window:
            return
        kind, angle = cue
        key = kind, (round(angle / 15) * 15) % 180
        if key not in self._handles:
            pixels = (ct.c_ubyte * (_SIZE * _SIZE * 4)).from_buffer_copy(_pixels(*key))
            image = _GLFWImage(_SIZE, _SIZE, pixels)
            self._handles[key] = self._glfw.glfwCreateCursor(
                ct.byref(image), _HOTSPOT, _HOTSPOT,
            )
        handle = self._handles[key]
        if not handle:
            self.reset()
            return
        if self._window is None:
            self._release_flag = not (self._config_flags.value & _NO_MOUSE_CURSOR_CHANGE)
            self._config_flags.value |= _NO_MOUSE_CURSOR_CHANGE
        if (window, handle) != (self._window, self._active_handle):
            self._glfw.glfwSetCursor(window, handle)
            self._window, self._active_handle = window, handle

    def reset(self):
        if self._window and self._glfw.glfwGetCurrentContext() == self._window:
            self._glfw.glfwSetCursor(self._window, None)
        if self._release_flag:
            self._config_flags.value &= ~_NO_MOUSE_CURSOR_CHANGE
            self._release_flag = False
        self._window = self._active_handle = None

    def close(self):
        self.reset()
        for handle in self._handles.values():
            if handle:
                self._glfw.glfwDestroyCursor(handle)
        self._handles.clear()
