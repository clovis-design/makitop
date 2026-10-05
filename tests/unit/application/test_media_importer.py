from concurrent.futures import ThreadPoolExecutor

import pytest

from makitop.application.media import MediaImporter
from makitop.model.project import Project


@pytest.fixture
def executor():
    with ThreadPoolExecutor(max_workers=2) as pool:
        yield pool


def test_import_de_plusieurs_fichiers(executor, video_file, audio_file, image_file):
    project = Project()
    importer = MediaImporter(lambda: project, executor)
    importer = MediaImporter(lambda: project, executor)
    imported = []
    importer.on_imported(imported.append)

    futures = importer.import_files([video_file, audio_file, image_file])
    results = [f.result(timeout=10) for f in futures]

    assert all(results)
    assert len(project.media) == 3
    assert {m.path for m in imported} == {video_file, audio_file, image_file}


def test_erreurs_signalees_sans_arreter_les_autres(executor, tmp_path, image_file):
    project = Project()
    importer = MediaImporter(lambda: project, executor)
    importer = MediaImporter(lambda: project, executor)
    failures = []
    importer.on_failed(lambda path, message: failures.append((path, message)))

    missing = tmp_path / "absent.mp4"
    futures = importer.import_files([missing, image_file])
    results = [f.result(timeout=10) for f in futures]

    assert results[0] is None
    assert results[1] is not None
    assert [p for p, _ in failures] == [missing]
    assert len(project.media) == 1


def test_doublon_signale(executor, image_file):
    project = Project()
    importer = MediaImporter(lambda: project, executor)
    importer = MediaImporter(lambda: project, executor)
    failures = []
    importer.on_failed(lambda path, message: failures.append(message))

    importer.import_files([image_file])[0].result(timeout=10)
    importer.import_files([image_file])[0].result(timeout=10)

    assert len(project.media) == 1
    assert failures and "Déjà importé" in failures[0]


def test_import_dans_le_projet_ouvert_au_moment_de_l_import(executor, image_file):
    first, second = Project(), Project()
    current = first
    importer = MediaImporter(lambda: current, executor)
    imported = []
    importer.on_imported(imported.append)

    importer.import_files([image_file])[0].result(timeout=10)
    current = second
    assert len(first.media) == 1
    assert second.media == []
    assert len(imported) == 1
