from dataclasses import replace

import pytest

from makitop.media.probe import probe
from makitop.model.keyframes import Keyframe, upsert, value_at
from makitop.model.timeline import ImageClip


@pytest.mark.parametrize("mode,expected", [("linear", 0.25), ("smooth", 0.15625),
                                          ("constant", 0)])
def test_interpolation_and_boundaries(mode, expected):
    keys = (Keyframe("x", 1, 0, mode), Keyframe("x", 3, 1))
    assert value_at(keys, "x", 1.5, 7) == expected
    assert value_at(keys, "x", -1, 7) == 0
    assert value_at(keys, "x", 3, 7) == 1
    assert value_at(keys, "x", 10, 7) == 1
    assert value_at(keys, "y", 2, 7) == 7


@pytest.mark.parametrize("args", [
    ("other", 0, 1), ("x", -1, 1), ("x", float("nan"), 1),
    ("width", 0, 0), ("volume", 0, 3), ("x", 0, float("inf")),
    ("x", 0, 1, "invalid"),
])
def test_invalid_keyframe_rejected(args):
    with pytest.raises(ValueError):
        Keyframe(*args)


def test_replace_key_without_duplicates_and_keep_other_properties():
    keys = (Keyframe("x", 1, 0), Keyframe("volume", 1, 0.5))
    updated = upsert(keys, Keyframe("x", 1, 0.75))
    assert len(updated) == 2
    assert value_at(updated, "x", 1, 0) == 0.75
    assert value_at(updated, "volume", 1, 0) == 0.5


def test_move_and_trim_clip_preserve_local_animation(image_file):
    clip = ImageClip(5, probe(image_file), 4, keyframes=(
        Keyframe("x", 0, 0), Keyframe("x", 4, 1),
    ))
    moved = replace(clip, timeline_start=12)
    assert moved.transform_at(2).x == 0.5
    shortened = replace(moved, display_duration=1)
    assert shortened.keyframes == clip.keyframes
    assert shortened.transform_at(0.5).x == 0.125
    with pytest.raises(ValueError, match="dupliquées"):
        replace(clip, keyframes=(Keyframe("x", 0, 0), Keyframe("x", 0, 1)))
