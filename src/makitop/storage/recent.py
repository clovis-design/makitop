"""Projets connus de l'application, avec leur date de dernière utilisation.

La liste est gardée dans le dossier de configuration de l'utilisateur. Un projet y entre
quand il est ouvert ou enregistré ; elle alimente la page d'accueil et le sous-menu
« Projets récents ».
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

MAX_PROJECTS = 100


def config_dir() -> Path:
    """Dossier de configuration de Makitop selon le système."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "Makitop"


@dataclass(frozen=True)
class RecentProject:
    path: Path
    # None pour une entrée écrite par une ancienne version, qui n'enregistrait pas la date.
    last_used: datetime | None = None

    @property
    def name(self) -> str:
        return self.path.stem


class RecentProjects:
    def __init__(self, file: Path) -> None:
        self._file = Path(file)
        self._entries = self._read()

    def entries(self) -> list[RecentProject]:
        """Projets qui existent encore, du plus récemment utilisé au plus ancien."""
        existing = [e for e in self._entries if e.path.is_file()]
        return sorted(existing, key=lambda e: e.last_used or datetime.min, reverse=True)

    def paths(self) -> list[Path]:
        return [entry.path for entry in self.entries()]

    def add(self, path: Path, when: datetime | None = None) -> None:
        """Ajoute le projet ou met à jour sa date de dernière utilisation."""
        path = Path(path).absolute()
        entry = RecentProject(path, when or datetime.now().replace(microsecond=0))
        others = [e for e in self._entries if e.path != path]
        self._entries = [entry, *others][:MAX_PROJECTS]
        self._write()

    def remove(self, path: Path) -> None:
        path = Path(path).absolute()
        self._entries = [e for e in self._entries if e.path != path]
        self._write()

    def _read(self) -> list[RecentProject]:
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            return [entry for item in data["recent"] if (entry := _entry_from_json(item))]
        except FileNotFoundError:
            return []
        except (OSError, ValueError, KeyError, TypeError):
            log.warning("Projets récents illisibles, liste réinitialisée : %s", self._file)
            return []

    def _write(self) -> None:
        # Perdre la liste des projets n'est pas grave : on ne bloque jamais l'utilisateur.
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            data = {"recent": [_entry_to_json(e) for e in self._entries]}
            self._file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            log.warning("Impossible d'enregistrer les projets récents dans %s", self._file)


def _entry_to_json(entry: RecentProject) -> dict:
    return {
        "path": str(entry.path),
        "last_used": entry.last_used.isoformat() if entry.last_used else None,
    }


def _entry_from_json(item) -> RecentProject | None:
    if isinstance(item, str):  # ancien format : simple liste de chemins
        return RecentProject(Path(item))
    if isinstance(item, dict) and isinstance(item.get("path"), str):
        last_used = item.get("last_used")
        return RecentProject(
            Path(item["path"]),
            datetime.fromisoformat(last_used) if isinstance(last_used, str) else None,
        )
    return None
