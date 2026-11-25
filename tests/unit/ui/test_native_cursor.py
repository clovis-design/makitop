from ctypes import c_int
from unittest.mock import Mock, call

from makitop.ui.native_cursor import NativeCursor


def test_native_cursor_is_set_reused_reset_and_freed():
    glfw = Mock()
    glfw.glfwGetCurrentContext.return_value = 10
    glfw.glfwCreateCursor.side_effect = [11, 12]
    flags = c_int(4)
    cursor = NativeCursor(glfw, flags)

    cursor.apply(("rotate", 0))
    assert flags.value == 4 | (1 << 5)
    cursor.apply(("resize", 90))
    cursor.apply(("resize", 91))
    flags.value |= 8
    cursor.reset()
    assert flags.value == 12
    cursor.close()

    assert glfw.glfwCreateCursor.call_count == 2
    assert glfw.glfwSetCursor.call_args_list == [
        call(10, 11), call(10, 12), call(10, None),
    ]
    assert glfw.glfwDestroyCursor.call_args_list == [call(11), call(12)]


def test_native_cursor_does_not_touch_glfw_without_current_viewport():
    glfw = Mock()
    glfw.glfwGetCurrentContext.return_value = None
    cursor = NativeCursor(glfw, c_int())

    cursor.apply(("move", 0))
    cursor.close()

    glfw.glfwCreateCursor.assert_not_called()
    glfw.glfwSetCursor.assert_not_called()
