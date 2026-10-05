from makitop.storage.recent import MAX_RECENT, RecentProjects


def _touch(path):
    path.write_text("{}", encoding="utf-8")
    return path


def test_plus_recent_en_premier_sans_doublon(tmp_path):
    a, b = _touch(tmp_path / "a.makitop"), _touch(tmp_path / "b.makitop")
    recent = RecentProjects(tmp_path / "recent.json")
    recent.add(a)
    recent.add(b)
    recent.add(a)
    assert recent.paths() == [a, b]
    assert recent.last() == a


def test_persiste_entre_deux_lancements(tmp_path):
    a = _touch(tmp_path / "a.makitop")
    RecentProjects(tmp_path / "config" / "recent.json").add(a)
    assert RecentProjects(tmp_path / "config" / "recent.json").paths() == [a]


def test_fichiers_supprimes_ignores(tmp_path):
    a = _touch(tmp_path / "a.makitop")
    recent = RecentProjects(tmp_path / "recent.json")
    recent.add(a)
    a.unlink()
    assert recent.paths() == []
    assert recent.last() is None


def test_taille_limitee(tmp_path):
    recent = RecentProjects(tmp_path / "recent.json")
    for i in range(MAX_RECENT + 3):
        recent.add(_touch(tmp_path / f"{i}.makitop"))
    assert len(recent.paths()) == MAX_RECENT


def test_fichier_de_config_corrompu(tmp_path):
    (tmp_path / "recent.json").write_text("n'importe quoi", encoding="utf-8")
    assert RecentProjects(tmp_path / "recent.json").paths() == []
