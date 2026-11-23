from PIL import Image

from makitop import app


def _logo(tmp_path, monkeypatch):
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(logo)
    monkeypatch.setattr(app, "LOGO", logo)
    monkeypatch.setattr(app, "config_dir", lambda: tmp_path / "config")
    return logo


def test_icone_ico_sous_windows(tmp_path, monkeypatch):
    _logo(tmp_path, monkeypatch)
    monkeypatch.setattr(app.sys, "platform", "win32")
    icon = app._window_icon()
    assert icon.endswith(".ico")
    with Image.open(icon) as image:
        assert image.format == "ICO"


def test_icone_png_sous_linux(tmp_path, monkeypatch):
    logo = _logo(tmp_path, monkeypatch)
    monkeypatch.setattr(app.sys, "platform", "linux")
    assert app._window_icon() == str(logo)
    assert not (tmp_path / "config").exists()  # aucune conversion


def test_icone_par_defaut_si_logo_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "LOGO", tmp_path / "absent.png")
    assert app._window_icon() == ""
