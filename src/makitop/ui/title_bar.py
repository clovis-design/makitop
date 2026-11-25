"""Barre de titre de la fenêtre, dessinée par l'application à la place de la barre native.

Elle contient le logo, les menus (éditeur seulement), le titre centré et les boutons
réduire / agrandir / fermer. La barre native étant masquée (`decorated=False`), le
déplacement, le double-clic pour agrandir et le redimensionnement par le bord droit, le bord
bas et le coin bas-droit sont gérés ici, image par image (`tick`).
"""

from collections.abc import Callable

import dearpygui.dearpygui as dpg
import numpy as np

from makitop.ui import menu_bar, win32_window
from makitop.ui.assets.style import COLORS, LOGO
from makitop.ui.layout import TITLE_BAR_HEIGHT
from makitop.ui.panels.transport_icons import icon_rgba

HEIGHT = TITLE_BAR_HEIGHT
MIN_WIDTH = 1500
MIN_HEIGHT = 600

TAG = "title_bar"
LOGO_BUTTON = "title_bar_logo"
LOGO_TEXTURE = "title_bar_logo_texture"
MENUS_GROUP = "title_bar_menus"
TITLE_TEXT = "title_bar_title"
BUTTONS = "title_bar_buttons"
MIN_BUTTON = "title_bar_minimize"
MAX_BUTTON = "title_bar_maximize"
MAX_HINT = "title_bar_maximize_hint"
CLOSE_BUTTON = "title_bar_close"
GRIP = "title_bar_resize_grip"
REGISTRY = "title_bar_texture_registry"

THEME = "title_bar_theme"
POPUP_THEME = "title_bar_popup_theme"
BUTTON_THEME = "title_bar_button_theme"
CLOSE_THEME = "title_bar_close_theme"
LOGO_THEME = "title_bar_logo_theme"

ICON_SIZE = 14
NAMES = ("minimize", "maximize", "restore", "close")
BUTTON_W = 46
BUTTON_H = 30
LOGO_SIZE = 20
EDGE = 6  # largeur (px) de la zone de redimensionnement le long des bords
_TEXT_H = 16

_on_close: Callable[[], None] | None = None
_hwnd: int | None = None
_title = ""
_width = 0
_height = 0
_visible = True
_maximized = False
_restore: tuple[int, int, int, int] | None = None  # (x, y, largeur, hauteur) avant agrandir
_drag: dict | None = None
_frames = 0
_FIT_FRAME = 3


# --- Icônes ----------------------------------------------------------------------------

def texture_tag(name: str) -> str:
    return f"title_bar_texture_{name}"


def _box(px, py, x0, y0, x1, y1):
    return (px > x0) & (px < x1) & (py > y0) & (py < y1)


def _mask(name, x, y):
    """Forme de l'icône ; on travaille en pixels (0 à 14) pour des traits de 1 px nets."""
    px, py = x * ICON_SIZE, y * ICON_SIZE
    if name == "minimize":
        return _box(px, py, 2, 7, 12, 8)
    if name == "maximize":
        return _box(px, py, 2, 2, 12, 12) & ~_box(px, py, 3, 3, 11, 11)
    if name == "restore":
        front_area = _box(px, py, 2, 4, 10, 12)
        front = front_area & ~_box(px, py, 3, 5, 9, 11)
        back = _box(px, py, 4, 2, 12, 10) & ~_box(px, py, 5, 3, 11, 9) & ~front_area
        return front | back
    if name == "close":
        inside = _box(px, py, 2.5, 2.5, 11.5, 11.5)
        # Seuil 1.1 et non 1 : les échantillons tombent pile sur 1, et l'arrondi flottant
        # rendrait la croix dissymétrique.
        return inside & ((np.abs(px - py) < 1.1) | (np.abs(px + py - ICON_SIZE) < 1.1))
    raise KeyError(name)


def _load_textures() -> None:
    if dpg.does_alias_exist(REGISTRY):
        return
    with dpg.texture_registry(tag=REGISTRY):
        for name in NAMES:
            dpg.add_static_texture(width=ICON_SIZE, height=ICON_SIZE,
                                   default_value=icon_rgba(name, ICON_SIZE, _mask),
                                   tag=texture_tag(name))
        image = dpg.load_image(str(LOGO)) if LOGO.exists() else None
        if image is not None:
            width, height, _channels, data = image
            dpg.add_static_texture(width=width, height=height, default_value=data,
                                   tag=LOGO_TEXTURE)


# --- Construction ----------------------------------------------------------------------

def create(
    actions: dict[str, Callable[[], None]] | None = None,
    shortcut_labels: dict[str, str] | None = None,
    on_close: Callable[[], None] | None = None,
) -> None:
    global _on_close, _maximized, _restore, _drag, _visible, _title, _frames
    _on_close = on_close
    _maximized, _restore, _drag, _visible, _title, _frames = False, None, None, True, "", 0
    _load_textures()
    _themes()
    # min_size : Dear PyGui impose 100 px de hauteur minimum par défaut.
    with dpg.window(tag=TAG, pos=(0, 0), width=MIN_WIDTH, height=HEIGHT, menubar=True,
                    min_size=(1, HEIGHT), max_size=(100_000, HEIGHT),
                    no_title_bar=True, no_move=True, no_resize=True, no_scrollbar=True,
                    no_collapse=True, no_saved_settings=True), dpg.menu_bar():
        if dpg.does_item_exist(LOGO_TEXTURE):
            # Bouton inerte : le cadre (FramePadding) centre le logo dans la hauteur.
            dpg.add_image_button(LOGO_TEXTURE, tag=LOGO_BUTTON,
                                 width=LOGO_SIZE, height=LOGO_SIZE)
            dpg.bind_item_theme(LOGO_BUTTON, LOGO_THEME)
        with dpg.group(tag=MENUS_GROUP, horizontal=True):
            menu_bar.add_menus(actions, shortcut_labels)
        for menu in dpg.get_item_children(MENUS_GROUP, 1):
            dpg.bind_item_theme(menu, POPUP_THEME)
        dpg.add_text("", tag=TITLE_TEXT, color=COLORS["label_muted"])
        with dpg.group(tag=BUTTONS, horizontal=True, horizontal_spacing=0,
                       pos=(MIN_WIDTH - 3 * BUTTON_W, (HEIGHT - BUTTON_H) // 2)):
            _window_button("minimize", MIN_BUTTON, "Réduire", _minimize)
            _window_button("maximize", MAX_BUTTON, "Agrandir", toggle_maximize,
                           hint_tag=MAX_HINT)
            _window_button("close", CLOSE_BUTTON, "Fermer", _close)
    dpg.bind_item_theme(TAG, THEME)
    dpg.bind_item_theme(BUTTONS, BUTTON_THEME)
    dpg.bind_item_theme(CLOSE_BUTTON, CLOSE_THEME)


def _window_button(name, tag, hint, callback, hint_tag=0) -> None:
    dpg.add_image_button(texture_tag(name), tag=tag, width=ICON_SIZE, height=ICON_SIZE,
                         callback=lambda *_: callback())
    with dpg.tooltip(tag):
        dpg.add_text(hint, tag=hint_tag)


def _themes() -> None:
    if dpg.does_alias_exist(THEME):
        return
    pad_x, pad_y = (BUTTON_W - ICON_SIZE) // 2, (BUTTON_H - ICON_SIZE) // 2
    with dpg.theme(tag=THEME), dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLORS["title_bar"])
        dpg.add_theme_color(dpg.mvThemeCol_MenuBarBg, COLORS["title_bar"])
        dpg.add_theme_color(dpg.mvThemeCol_Text, COLORS["text_main"])
        dpg.add_theme_color(dpg.mvThemeCol_PopupBg, COLORS["bg_main"])
        dpg.add_theme_color(dpg.mvThemeCol_Border, COLORS["section_header"])
        dpg.add_theme_color(dpg.mvThemeCol_Header, COLORS["accent"])
        dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, COLORS["section_hover"])
        dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, COLORS["accent"])
        dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
        dpg.add_theme_style(dpg.mvStyleVar_WindowBorderSize, 0)
        dpg.add_theme_style(dpg.mvStyleVar_WindowMinSize, 1, 1)
        # Hauteur de la barre de menus = police + 2 × FramePadding.y = 36 px.
        dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, (HEIGHT - _TEXT_H) // 2)
        dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 0)
    # Les menus déroulants retrouvent des marges normales.
    with dpg.theme(tag=POPUP_THEME), dpg.theme_component(dpg.mvAll):
        dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 8, 8)
        dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 6, 4)
        dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 6)
        dpg.add_theme_style(dpg.mvStyleVar_PopupRounding, 6)
        dpg.add_theme_style(dpg.mvStyleVar_PopupBorderSize, 1)
    with dpg.theme(tag=LOGO_THEME), dpg.theme_component(dpg.mvImageButton):
        for color in (dpg.mvThemeCol_Button, dpg.mvThemeCol_ButtonHovered,
                      dpg.mvThemeCol_ButtonActive):
            dpg.add_theme_color(color, (0, 0, 0, 0))
        dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, (HEIGHT - LOGO_SIZE) // 2)
    for tag, hovered, active in (
        (BUTTON_THEME, COLORS["section_hover"], COLORS["accent"]),
        (CLOSE_THEME, COLORS["danger_hover"], COLORS["danger"]),
    ):
        with dpg.theme(tag=tag), dpg.theme_component(dpg.mvImageButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hovered)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, active)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, pad_x, pad_y)


def setup_window(hwnd: int | None) -> None:
    """À appeler après `dpg.show_viewport()` : style Windows et poignée de redimensionnement."""
    global _hwnd
    _hwnd = hwnd
    win32_window.style_window(hwnd, COLORS["section_header"])
    if not dpg.does_item_exist(GRIP):
        dpg.add_viewport_drawlist(front=True, tag=GRIP)
    resize(dpg.get_viewport_client_width(), dpg.get_viewport_client_height())


def _fit_to_screen() -> None:
    """Fenêtre plus grande que l'écran (petit écran, mise à l'échelle Windows) : les boutons
    seraient hors de l'écran, on l'agrandit donc à la zone de travail."""
    area, rect = win32_window.work_area(_hwnd), win32_window.window_rect(_hwnd)
    if area and rect and not _maximized and (rect[2] > area[2] or rect[3] > area[3]):
        toggle_maximize()


# --- État affiché ----------------------------------------------------------------------

def set_title(text: str) -> None:
    global _title
    _title = text
    if dpg.does_item_exist(TITLE_TEXT):
        dpg.set_value(TITLE_TEXT, text)
        _place_title()
    if dpg.is_viewport_ok():
        dpg.set_viewport_title(text)  # barre des tâches


def show_menus(visible: bool) -> None:
    if dpg.does_item_exist(MENUS_GROUP):
        dpg.configure_item(MENUS_GROUP, show=visible)


def set_visible(visible: bool) -> None:
    """Masquée pendant le plein écran du viewer."""
    global _visible
    _visible = visible
    if dpg.does_item_exist(TAG):
        dpg.configure_item(TAG, show=visible)
    _draw_grip()


def is_maximized() -> bool:
    return _maximized


def resize(width: int, height: int) -> None:
    global _width, _height
    _width, _height = width, height
    if not dpg.does_item_exist(TAG):
        return
    dpg.configure_item(TAG, width=width)
    dpg.configure_item(BUTTONS, pos=(width - 3 * BUTTON_W, (HEIGHT - BUTTON_H) // 2))
    _place_title()
    _draw_grip()


def _place_title() -> None:
    size = dpg.get_text_size(_title) if dpg.is_viewport_ok() else None
    text_w = size[0] if size else len(_title) * 7
    left = _content_left() + 24
    x = max(left, (_width - text_w) // 2)
    # y = 0 : dans une barre de menus, ImGui centre déjà le texte (AlignTextToFramePadding).
    dpg.configure_item(TITLE_TEXT, pos=(int(x), 0))


def _content_left() -> int:
    """Bord droit du logo et des menus : la zone libre (titre, déplacement) commence là."""
    for tag in (MENUS_GROUP, LOGO_BUTTON):
        if dpg.does_item_exist(tag) and dpg.is_item_shown(tag):
            right = dpg.get_item_rect_max(tag)[0]
            if right:
                return right
    return 0


def _draw_grip() -> None:
    if not dpg.does_item_exist(GRIP):
        return
    dpg.delete_item(GRIP, children_only=True)
    if not _visible or _maximized or not _width:
        return
    color = (*COLORS["label_muted"][:3], 150)
    for offset in (4, 8, 12):
        dpg.draw_line((_width - offset, _height - 2), (_width - 2, _height - offset),
                      color=color, thickness=1, parent=GRIP)


# --- Boutons ---------------------------------------------------------------------------

def _minimize() -> None:
    if dpg.is_viewport_ok():
        dpg.minimize_viewport()


def _close() -> None:
    if _on_close is not None:
        _on_close()


def toggle_maximize() -> None:
    """Agrandit à la zone de travail de l'écran (barre des tâches visible) ou restaure."""
    global _maximized, _restore
    if not dpg.is_viewport_ok():
        return
    if _maximized and _restore is not None:
        _set_geometry(*_restore)
        _maximized = False
    else:
        _restore = _geometry()
        area = win32_window.work_area(_hwnd)
        if area is not None:
            _set_geometry(*area)
        else:
            dpg.maximize_viewport()
        _maximized = True
    dpg.configure_item(MAX_BUTTON, texture_tag=texture_tag(
        "restore" if _maximized else "maximize"))
    dpg.set_value(MAX_HINT, "Restaurer" if _maximized else "Agrandir")
    _draw_grip()


def _geometry() -> tuple[int, int, int, int]:
    """(x, y, largeur, hauteur) de la fenêtre."""
    rect = win32_window.window_rect(_hwnd)
    if rect is not None:
        return rect
    x, y = dpg.get_viewport_pos()
    return int(x), int(y), dpg.get_viewport_width(), dpg.get_viewport_height()


def _set_geometry(x, y, width=None, height=None) -> None:
    """Sans taille : déplace seulement. Sous Windows on passe par SetWindowPos, car
    set_viewport_pos de Dear PyGui décale l'abscisse demandée."""
    if win32_window.set_window_rect(_hwnd, x, y, width, height):
        return
    if width is not None:
        dpg.set_viewport_width(int(width))
        dpg.set_viewport_height(int(height))
    dpg.set_viewport_pos([int(x), int(y)])


# --- Souris : déplacer, agrandir, redimensionner ---------------------------------------

def tick() -> None:
    """À appeler à chaque image, avant `render_dearpygui_frame`."""
    global _drag, _frames
    _frames += 1
    if _frames == _FIT_FRAME:
        # Pas dans setup_window : Dear PyGui réapplique sa position de départ aux
        # premières images.
        _fit_to_screen()
    if not dpg.is_viewport_ok() or not _visible:
        _drag = None
        return
    if _drag is not None:
        _continue_drag()
        return
    if not dpg.is_mouse_button_clicked(dpg.mvMouseButton_Left):
        return
    x, y = dpg.get_mouse_pos(local=False)
    width, height = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
    right, bottom = x >= width - EDGE, y >= height - EDGE
    if (right or bottom) and not _maximized:
        _start_drag(("resize", right, bottom))
    elif _in_move_zone(x, y):
        if dpg.is_mouse_button_double_clicked(dpg.mvMouseButton_Left):
            toggle_maximize()
        elif not _maximized:
            _start_drag("move")


def _in_move_zone(x: float, y: float) -> bool:
    """Partie libre de la barre : ni logo, ni menus, ni boutons."""
    return (0 <= y < HEIGHT and dpg.is_item_hovered(TAG)
            and _content_left() < x < _width - 3 * BUTTON_W)


def _start_drag(mode) -> None:
    global _drag
    _drag = {
        "mode": mode,
        "screen": win32_window.cursor_pos(),
        "mouse": tuple(dpg.get_mouse_pos(local=False)),
        "geometry": _geometry(),
    }


def _continue_drag() -> None:
    global _drag
    if not dpg.is_mouse_button_down(dpg.mvMouseButton_Left):
        _drag = None
        return
    mouse = tuple(dpg.get_mouse_pos(local=False))
    screen = win32_window.cursor_pos() if _drag["screen"] is not None else None
    if screen is not None:
        dx, dy = screen[0] - _drag["screen"][0], screen[1] - _drag["screen"][1]
    else:
        dx, dy = mouse[0] - _drag["mouse"][0], mouse[1] - _drag["mouse"][1]

    start_x, start_y, start_w, start_h = _drag["geometry"]
    if _drag["mode"] == "move":
        if screen is not None:
            x, y = start_x + dx, start_y + dy
        else:
            # Sans position écran : la souris relative revient à l'ancre quand la fenêtre
            # l'a rattrapée ; on n'applique l'écart que si la souris a vraiment bougé.
            if mouse == _drag.get("last"):
                return
            _drag["last"] = mouse
            x, y = _geometry()[0] + dx, _geometry()[1] + dy
        if (int(x), int(y)) != _geometry()[:2]:
            _set_geometry(x, y)
        return

    _, right, bottom = _drag["mode"]
    width = max(MIN_WIDTH, int(start_w + dx)) if right else start_w
    height = max(MIN_HEIGHT, int(start_h + dy)) if bottom else start_h
    if (width, height) != _geometry()[2:]:
        _set_geometry(start_x, start_y, width, height)
