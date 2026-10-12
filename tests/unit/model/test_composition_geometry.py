import pytest

from makitop.model.composition import Transform, drag_transform, fitted_bounds


def test_resize_keeps_aspect_ratio_and_opposite_corner():
    original = Transform(x=0.2, y=0.3, width=0.4, height=0.2)
    changed = drag_transform(original, (0.2, 0.3, 0.4, 0.2),
                             "resize", "top_left", -0.1, -0.1, 16 / 9)
    assert changed.width / changed.height == pytest.approx(2)
    assert changed.x + changed.width == pytest.approx(0.6)
    assert changed.y + changed.height == pytest.approx(0.5)
    assert changed.width > original.width


def test_crop_changes_visible_source_without_stretching():
    original = Transform()
    cropped = drag_transform(original, (0, 0, 1, 1), "crop", "left", 0.25, 0, 1)
    assert cropped.crop_left == 0.25
    assert cropped.x == 0.25
    assert cropped.width == 0.75
    assert fitted_bounds(cropped, 100, 100, 1) == pytest.approx((0.25, 0, 0.75, 1))
    restored = drag_transform(cropped, (0.25, 0, 0.75, 1), "crop", "left", -0.25, 0, 1)
    assert restored == original


@pytest.mark.parametrize("values", [
    {"width": 0}, {"x": float("nan")}, {"crop_left": -0.1},
    {"crop_left": 0.5, "crop_right": 0.5},
])
def test_invalid_geometry(values):
    with pytest.raises(ValueError):
        Transform(**values)
