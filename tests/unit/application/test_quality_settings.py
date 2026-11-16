import pytest

from makitop.application.composition import CompositionEditor
from makitop.application.projects import ProjectSession
from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.media.probe import probe
from makitop.storage import project_file
from makitop.storage.recent import RecentProjects


def test_fps_settings_preserve_timing_and_survive_save(tmp_path, video_file):
    session = ProjectSession(RecentProjects(tmp_path / "recent.json"))
    playback = TimelinePlaybackController()
    editor = CompositionEditor(session, playback)
    try:
        assert session.project.timeline.fps == 60
        media = probe(video_file)
        session.project.media.append(media)
        clip = editor.add_media(media)
        editor.set_fps(120)
        assert playback.project.timeline.fps == 120
        assert (clip.timeline_start, clip.source_start, clip.duration) == (0, 0, media.duration)
        session.save_as(tmp_path / "project.makitop")
        assert project_file.load(session.path).timeline.fps == 120
        with pytest.raises(ValueError):
            editor.set_fps(121)
        assert session.project.timeline.fps == 120
        editor.preview_source(media)
        assert playback.project.timeline.fps == 10  # cadence native de la source
    finally:
        playback.close()
