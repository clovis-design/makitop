import numpy as np
import pytest

from makitop.application.playback import PlaybackController


def test_lecteur_vide():
    controller = PlaybackController()
    controller.play()
    controller.pause()
    controller.stop()
    assert controller.current_time() == 0
    assert controller.current_frame() is None
    controller.close()


def test_charger_lire_et_remplacer_video(video_file):
    controller = PlaybackController()
    try:
        first, duration = controller.load(video_file)
        assert first.shape == (48, 64, 3)
        assert duration >= 1
        assert controller.current_time() == 0
        controller.seek(0.5)
        assert controller.current_frame().mean() > first.mean()
        controller.stop()
        np.testing.assert_array_equal(controller.current_frame(), first)
        old_decoder = controller.decoder
        controller.load(video_file)
        assert old_decoder.container is None
        assert controller.current_time() == 0
    finally:
        controller.close()


def test_echec_chargement_conserve_video(video_file, tmp_path):
    controller = PlaybackController()
    try:
        first, _ = controller.load(video_file)
        with pytest.raises(FileNotFoundError):
            controller.load(tmp_path / "absent.mp4")
        np.testing.assert_array_equal(controller.current_frame(), first)
    finally:
        controller.close()
