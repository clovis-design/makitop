import pytest

from makitop.application.composition import CompositionEditor
from makitop.application.projects import ProjectSession
from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.media.probe import probe
from makitop.storage.recent import RecentProjects


@pytest.fixture
def editor(tmp_path):
    player = TimelinePlaybackController()
    editor = CompositionEditor(ProjectSession(RecentProjects(tmp_path / "recent.json")), player)
    try:
        yield editor
    finally:
        player.close()


def test_ajout_reglage_et_suppression_d_effets(editor, image_file):
    media = probe(image_file)
    editor.project.media.append(media)
    clip = editor.add_media(media)
    editor.select(None)
    with pytest.raises(ValueError, match="Sélectionnez"):
        editor.add_effect("bw")
    editor.select(clip.id)
    editor.session._dirty = False  # l'ajout du clip a déjà marqué le projet
    editor.add_effect("bw")
    editor.add_effect("blur")
    assert editor.session.dirty
    with pytest.raises(ValueError, match="déjà"):
        editor.add_effect("bw")
    editor.update_effect(1, 0.8)
    assert [(e.kind, e.amount) for e in editor.selected.effects] == [("bw", 1), ("blur", 0.8)]
    with pytest.raises(ValueError):
        editor.update_effect(1, 3)
    editor.remove_effect(0)
    assert [e.kind for e in editor.selected.effects] == ["blur"]
