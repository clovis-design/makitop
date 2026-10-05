import dearpygui.dearpygui as dpg
import pytest

from makitop.ui import main_window, menu_bar, shortcuts


@pytest.fixture
def context():
    dpg.create_context()
    yield
    dpg.destroy_context()


def _actions(calls):
    return {
        item: (lambda item=item: calls.append(item))
        for item in (
            menu_bar.NEW_PROJECT,
            menu_bar.OPEN_PROJECT,
            menu_bar.SAVE_PROJECT,
            menu_bar.SAVE_PROJECT_AS,
            menu_bar.IMPORT_MEDIA,
        )
    }


@pytest.mark.parametrize(
    ("key", "shift", "expected"),
    [
        (dpg.mvKey_N, False, menu_bar.NEW_PROJECT),
        (dpg.mvKey_O, False, menu_bar.OPEN_PROJECT),
        (dpg.mvKey_S, False, menu_bar.SAVE_PROJECT),
        (dpg.mvKey_S, True, menu_bar.SAVE_PROJECT_AS),
        (dpg.mvKey_I, False, menu_bar.IMPORT_MEDIA),
    ],
)
def test_raccourcis(key, shift, expected):
    calls = []
    shortcuts.find_action(key, ctrl=True, shift=shift, actions=_actions(calls))()
    assert calls == [expected]


def test_touche_seule_ou_sans_action_ignoree():
    assert shortcuts.find_action(dpg.mvKey_S, ctrl=False, shift=False, actions=_actions([])) is None
    assert shortcuts.find_action(dpg.mvKey_S, ctrl=True, shift=False, actions={}) is None


def test_raccourcis_affiches_dans_le_menu(context):
    main_window.build(actions=_actions([]))
    config = dpg.get_item_configuration(menu_bar.item_tag(menu_bar.SAVE_PROJECT_AS))
    assert config["shortcut"] == "Ctrl+Maj+S"
    assert dpg.does_item_exist(shortcuts.HANDLER_TAG)
