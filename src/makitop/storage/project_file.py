"""Lecture et écriture des fichiers de projet `.makitop` (JSON).

Format (version 2) :

    {
      "format": "makitop",
      "version": 2,
      "name": "Mon film",
      "media": [{"type": "video", "path": "rushs/plage.mp4", "id": "...", ...}],
      "timeline": [
        {
          "clip_type": "media",
          "id": "...",
          "timeline_start": 0.0,
          "media_id": "...",
          "source_start": 0.0,
          "source_end": 10.5
        }
      ]
    }

Les chemins des médias situés dans le dossier du projet (ou un sous-dossier) sont
enregistrés en relatif, pour qu'on puisse déplacer le dossier entier ; les autres
restent absolus.
"""

import json
import os
from pathlib import Path

from makitop.model.media import Media, MediaKind
from makitop.model.project import Project
from makitop.model.timeline import BaseClip, ImageClip, MediaClip, Timeline

EXTENSION = ".makitop"
FORMAT = "makitop"
VERSION = 2


class ProjectFileError(Exception):
    """Le fichier de projet est introuvable, illisible ou d'un format inconnu."""


def save(project: Project, path: Path) -> None:
    """Écrit le projet. L'écriture passe par un fichier temporaire : un plantage
    pendant la sauvegarde ne corrompt pas le fichier existant."""
    path = Path(path)
    media_index = {m.id: m for m in project.media}
    data = {
        "format": FORMAT,
        "version": VERSION,
        "name": project.name,
        "media": [_media_to_dict(m, path.parent) for m in project.media],
        "timeline": [_clip_to_dict(c) for c in project.timeline.clips],
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
        media_index = {m.id: m for m in media}
        clips = [_clip_from_dict(c, media_index) for c in data.get("timeline", [])]
    except (KeyError, TypeError, ValueError) as error:
        raise ProjectFileError(f"Projet corrompu : {path.name}") from error
    return Project(
        name=str(data.get("name") or path.stem),
        media=media,
        timeline=Timeline(clips=clips),
    )


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


def _clip_to_dict(clip: BaseClip) -> dict:
    if isinstance(clip, MediaClip):
        return {
            "clip_type": "media",
            "id": clip.id,
            "timeline_start": clip.timeline_start,
            "media_id": clip.media.id,
            "source_start": clip.source_start,
            "source_end": clip.source_end,
        }
    if isinstance(clip, ImageClip):
        return {
            "clip_type": "image",
            "id": clip.id,
            "timeline_start": clip.timeline_start,
            "media_id": clip.media.id,
            "display_duration": clip.display_duration,
        }
    raise ValueError(f"Type de clip inconnu : {type(clip)}")


def _clip_from_dict(data: dict, media_index: dict[str, Media]) -> BaseClip:
    clip_type = data["clip_type"]
    media = media_index[data["media_id"]]
    if clip_type == "media":
        return MediaClip(
            timeline_start=float(data["timeline_start"]),
            media=media,
            source_start=float(data["source_start"]),
            source_end=float(data["source_end"]),
            id=data["id"],
        )
    if clip_type == "image":
        return ImageClip(
            timeline_start=float(data["timeline_start"]),
            media=media,
            display_duration=float(data["display_duration"]),
            id=data["id"],
        )
    raise ValueError(f"Type de clip inconnu : {clip_type!r}")


def _portable_path(path: Path, project_dir: Path) -> str:
    path, project_dir = Path(path).absolute(), Path(project_dir).absolute()
    if path.is_relative_to(project_dir):
        return path.relative_to(project_dir).as_posix()
    return str(path)
