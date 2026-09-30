"""Liste des projets récents, gardée dans le dossier de configuration de l'utilisateur."""

import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

MAX_RECENT = 10


def config_dir() -> Path:
    """Dossier de configuration de Makitop selon le système."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "Makitop"


class RecentProjects:
    def __init__(self, file: Path) -> None:
        self._file = Path(file)
        self._paths = self._read()

    def paths(self) -> list[Path]:
        """Projets récents qui existent encore, du plus récent au plus ancien."""
        return [p for p in self._paths if p.is_file()]

    def last(self) -> Path | None:
        return next(iter(self.paths()), None)

    def add(self, path: Path) -> None:
        path = Path(path).absolute()
        self._paths = [path, *(p for p in self._paths if p != path)][:MAX_RECENT]
        self._write()

    def remove(self, path: Path) -> None:
        path = Path(path).absolute()
        self._paths = [p for p in self._paths if p != path]
        self._write()

    def _read(self) -> list[Path]:
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            return [Path(p) for p in data["recent"] if isinstance(p, str)]
        except FileNotFoundError:
            return []
        except (OSError, ValueError, KeyError, TypeError):
            log.warning("Projets récents illisibles, liste réinitialisée : %s", self._file)
            return []

    def _write(self) -> None:
        # Perdre la liste des récents n'est pas grave : on ne bloque jamais l'utilisateur.
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            data = {"recent": [str(p) for p in self._paths]}
            self._file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            log.warning("Impossible d'enregistrer les projets récents dans %s", self._file)
