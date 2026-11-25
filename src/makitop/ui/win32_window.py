"""Réglages Windows de la fenêtre sans bordure native (coins arrondis, zone de travail, curseur).

Chaque fonction ne fait rien hors de Windows et ignore les erreurs : ces réglages sont
cosmétiques, l'application doit fonctionner sans eux (Windows 10, Linux, macOS).
"""

import ctypes
import functools
import logging
import os
import sys

log = logging.getLogger(__name__)

_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWCP_ROUND = 2
_DWMWA_BORDER_COLOR = 34
_MONITOR_DEFAULTTONEAREST = 2
_SWP_NOSIZE = 0x0001
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010


@functools.cache
def _user32():
    if sys.platform != "win32":
        return None
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    return user32


def find_hwnd(title_prefix: str) -> int | None:
    """Fenêtre visible de ce processus dont le titre commence par `title_prefix`."""
    user32 = _user32()
    if user32 is None:
        return None
    from ctypes import wintypes

    found = []
    pid = os.getpid()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            text = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, text, 256)
            if text.value.startswith(title_prefix):
                found.append(hwnd)
                return False
        return True

    try:
        user32.EnumWindows(visit, 0)
    except OSError:
        log.exception("Fenêtre introuvable")
    return found[0] if found else None


def style_window(hwnd: int | None, border_rgb: tuple[int, int, int]) -> None:
    """Coins arrondis et bordure fine colorée (Windows 11 ; ignoré ailleurs)."""
    if hwnd is None or sys.platform != "win32":
        return
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        r, g, b = border_rgb[:3]
        for attribute, value in ((_DWMWA_WINDOW_CORNER_PREFERENCE, _DWMWCP_ROUND),
                                 (_DWMWA_BORDER_COLOR, r | (g << 8) | (b << 16))):
            data = ctypes.c_int(value)
            dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attribute,
                                         ctypes.byref(data), ctypes.sizeof(data))
    except OSError:
        log.info("Style DWM indisponible (Windows 10 ou antérieur ?)")


def work_area(hwnd: int | None) -> tuple[int, int, int, int] | None:
    """(x, y, largeur, hauteur) de l'écran de la fenêtre, sans la barre des tâches."""
    user32 = _user32()
    if user32 is None or hwnd is None:
        return None
    from ctypes import wintypes

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    info = MonitorInfo(cbSize=ctypes.sizeof(MonitorInfo))
    monitor = user32.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONEAREST)
    if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    rect = info.rcWork
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def window_rect(hwnd: int | None) -> tuple[int, int, int, int] | None:
    """(x, y, largeur, hauteur) réels de la fenêtre."""
    user32 = _user32()
    if user32 is None or hwnd is None:
        return None
    from ctypes import wintypes

    rect = wintypes.RECT()
    if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def set_window_rect(hwnd: int | None, x: int, y: int, width: int | None = None,
                    height: int | None = None) -> bool:
    """Déplace (et redimensionne si une taille est donnée) la fenêtre.

    Dear PyGui décale l'abscisse demandée à set_viewport_pos ; on passe donc par Windows.
    Renvoie False hors Windows, l'appelant utilise alors l'API de Dear PyGui.
    """
    user32 = _user32()
    if user32 is None or hwnd is None:
        return False
    from ctypes import wintypes

    flags = _SWP_NOZORDER | _SWP_NOACTIVATE | (_SWP_NOSIZE if width is None else 0)
    return bool(user32.SetWindowPos(wintypes.HWND(hwnd), None, int(x), int(y),
                                    int(width or 0), int(height or 0), flags))


def cursor_pos() -> tuple[int, int] | None:
    """Position du curseur à l'écran : stable même quand la fenêtre bouge sous lui."""
    user32 = _user32()
    if user32 is None:
        return None
    from ctypes import wintypes

    point = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        return None
    return point.x, point.y
