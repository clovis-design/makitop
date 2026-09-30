"""Outils communs aux dialogues de fichiers Dear PyGui."""

from pathlib import Path


def chosen_path(app_data: dict) -> Path | None:
    """Fichier choisi dans un dialogue à fichier unique : celui cliqué, sinon le nom tapé."""
    selections = app_data.get("selections") or {}
    if selections:
        return Path(next(iter(selections.values())))
    if (app_data.get("file_name") or "").strip():
        return Path(app_data["file_path_name"])
    return None
