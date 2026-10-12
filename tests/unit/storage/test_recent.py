import json
from datetime import datetime

from makitop.storage.recent import MAX_PROJECTS, RecentProjects


def _touch(path):
    path.write_text("{}", encoding="utf-8")
    return path


def test_plus_recent_en_premier_sans_doublon(tmp_path):
    a, b = _touch(tmp_path / "a.makitop"), _touch(tmp_path / "b.makitop")
    recent = RecentProjects(tmp_path / "recent.json")
    recent.add(a, datetime(2026, 10, 1, 9, 0))
    recent.add(b, datetime(2026, 10, 2, 9, 0))
    recent.add(a, datetime(2026, 10, 3, 9, 0))
    assert recent.paths() == [a, b]
    assert [e.last_used for e in recent.entries()] == [
        datetime(2026, 10, 3, 9, 0),
        datetime(2026, 10, 2, 9, 0),
    ]


def test_tri_par_date_meme_si_ajoute_dans_le_desordre(tmp_path):
    a, b = _touch(tmp_path / "a.makitop"), _touch(tmp_path / "b.makitop")
    recent = RecentProjects(tmp_path / "recent.json")
    recent.add(a, datetime(2026, 10, 5))
    recent.add(b, datetime(2026, 9, 1))  # ajouté après, mais utilisé avant
    assert recent.paths() == [a, b]


def test_date_par_defaut_maintenant(tmp_path):
    a = _touch(tmp_path / "a.makitop")
    recent = RecentProjects(tmp_path / "recent.json")
    before = datetime.now().replace(microsecond=0)
    recent.add(a)
    assert recent.entries()[0].last_used >= before
    assert recent.entries()[0].name == "a"


def test_persiste_entre_deux_lancements(tmp_path):
    a = _touch(tmp_path / "a.makitop")
    when = datetime(2026, 10, 7, 16, 30)
    RecentProjects(tmp_path / "config" / "recent.json").add(a, when)
    entries = RecentProjects(tmp_path / "config" / "recent.json").entries()
    assert [(e.path, e.last_used) for e in entries] == [(a, when)]


def test_ancien_format_sans_date(tmp_path):
    a = _touch(tmp_path / "a.makitop")
    (tmp_path / "recent.json").write_text(json.dumps({"recent": [str(a)]}), encoding="utf-8")
    entries = RecentProjects(tmp_path / "recent.json").entries()
    assert [(e.path, e.last_used) for e in entries] == [(a, None)]


def test_fichiers_supprimes_ignores(tmp_path):
    a = _touch(tmp_path / "a.makitop")
    recent = RecentProjects(tmp_path / "recent.json")
    recent.add(a)
    a.unlink()
    assert recent.entries() == []


def test_retirer(tmp_path):
    a = _touch(tmp_path / "a.makitop")
    recent = RecentProjects(tmp_path / "recent.json")
    recent.add(a)
    recent.remove(a)
    assert recent.paths() == []


def test_taille_limitee(tmp_path):
    recent = RecentProjects(tmp_path / "recent.json")
    for i in range(MAX_PROJECTS + 3):
        recent.add(_touch(tmp_path / f"{i}.makitop"))
    assert len(recent.entries()) == MAX_PROJECTS


def test_fichier_de_config_corrompu(tmp_path):
    (tmp_path / "recent.json").write_text("n'importe quoi", encoding="utf-8")
    assert RecentProjects(tmp_path / "recent.json").entries() == []
