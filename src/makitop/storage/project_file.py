"""Lecture et écriture des fichiers de projet `.makitop` (JSON).

Format (version 2 ; lecture des anciens projets version 1 conservée) :

    {
      "format": "makitop",
      "version": 2,
      "name": "Mon film",
      "media": [{"type": "video", "path": "rushs/plage.mp4", "id": "...", ...}],
      "timeline": {"fps": 30, "clips": [...]}
    }

Les chemins des médias situés dans le dossier du projet (ou un sous-dossier) sont
enregistrés en relatif, pour qu'on puisse déplacer le dossier entier ; les autres
restent absolus.
"""

import json
import os
from dataclasses import asdict
from pathlib import Path

from makitop.model.media import Media, MediaKind
from makitop.model.project import Project
from makitop.model.timeline import Clip, Timeline

EXTENSION = ".makitop"
FORMAT = "makitop"
VERSION = 2


class ProjectFileError(Exception):
    """Le fichier de projet est introuvable, illisible ou d'un format inconnu."""


def save(project: Project, path: Path) -> None:
    """Écrit le projet. L'écriture passe par un fichier temporaire : un plantage
    pendant la sauvegarde ne corrompt pas le fichier existant."""
    path = Path(path)
    data = {
        "format": FORMAT,
        "version": VERSION,
        "name": project.name,
        "media": [_media_to_dict(m, path.parent) for m in project.media],
        "timeline": asdict(project.timeline),
    }
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as error:
        tmp.unlink(missing_ok=True)
        raise ProjectFileError(
            f"Impossible d'enregistrer {path.name} : {error.strerror}"
        ) from error


def load(path: Path) -> Project:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ProjectFileError(f"Projet introuvable : {path.name}") from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProjectFileError(f"Projet illisible : {path.name}") from error

    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ProjectFileError(f"Ce n'est pas un projet Makitop : {path.name}")
    version = data.get("version")
    if not isinstance(version, int) or version > VERSION:
        raise ProjectFileError(
            f"{path.name} a été créé par une version plus récente de Makitop (format {version})."
        )

    try:
        media = [_media_from_dict(m, path.parent) for m in data.get("media", [])]
        raw = data.get("timeline", {})
        timeline = Timeline(
            clips=[Clip(**clip) for clip in raw.get("clips", [])],
            fps=raw.get("fps", 30),
        )
        videos = {m.id for m in media if m.kind is MediaKind.VIDEO}
        if any(c.media_id not in videos for c in timeline.clips):
            raise ValueError("Un clip référence une vidéo inconnue.")
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise ProjectFileError(f"Projet corrompu : {path.name}") from error
    return Project(name=str(data.get("name") or path.stem), media=media, timeline=timeline)


def _media_to_dict(media: Media, project_dir: Path) -> dict:
    data: dict = {
        "type": media.kind.value,
        "path": _portable_path(media.path, project_dir),
        "id": media.id,
    }
    for field in ("duration", "width", "height", "fps", "video_codec",
                  "audio_codec", "sample_rate", "channels"):
        value = getattr(media, field)
        if value is not None:
            data[field] = value
    return data


def _media_from_dict(data: dict, project_dir: Path) -> Media:
    data = dict(data)
    kind = MediaKind(data.pop("type"))
    path = Path(data.pop("path"))
    if not path.is_absolute():
        path = project_dir / path
    return Media(path=path, kind=kind, **data)


def _portable_path(path: Path, project_dir: Path) -> str:
    path, project_dir = Path(path).absolute(), Path(project_dir).absolute()
    if path.is_relative_to(project_dir):
        return path.relative_to(project_dir).as_posix()
    return str(path)
