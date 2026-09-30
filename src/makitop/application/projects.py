"""Projet ouvert : création, ouverture, enregistrement et suivi des modifications.

Les écouteurs peuvent être appelés depuis un thread de travail (par exemple quand un
import marque le projet comme modifié) : ils doivent rester thread-safe.
"""

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from makitop.media.probe import MediaProbeError, probe
from makitop.model.media import Media
from makitop.model.project import Project
from makitop.storage import project_file
from makitop.storage.recent import RecentProjects

log = logging.getLogger(__name__)

ProjectListener = Callable[[Project], None]
StateListener = Callable[[], None]
MediaListener = Callable[[list[Media]], None]

_KIND_NAMES = {"Video": "une vidéo", "Audio": "un fichier audio", "Image": "une image"}


class ProjectSession:
    def __init__(self, recent: RecentProjects) -> None:
        self.recent = recent
        self._project = Project()
        self._path: Path | None = None
        self._dirty = False
        self._lock = threading.Lock()
        self._project_listeners: list[ProjectListener] = []
        self._state_listeners: list[StateListener] = []
        self._media_listeners: list[MediaListener] = []

    @property
    def project(self) -> Project:
        return self._project

    @property
    def path(self) -> Path | None:
        """Fichier .makitop du projet, ou None s'il n'a jamais été enregistré."""
        return self._path

    @property
    def dirty(self) -> bool:
        """Vrai si le projet a des modifications non enregistrées."""
        return self._dirty

    @property
    def title(self) -> str:
        return self._project.name + (" *" if self._dirty else "")

    def on_project_changed(self, listener: ProjectListener) -> None:
        """Appelé quand un autre projet devient le projet ouvert (nouveau ou ouverture)."""
        self._project_listeners.append(listener)

    def on_state_changed(self, listener: StateListener) -> None:
        """Appelé quand le nom, le fichier ou l'état « modifié » du projet change."""
        self._state_listeners.append(listener)

    def on_media_relinked(self, listener: MediaListener) -> None:
        """Appelé avec les médias qui viennent d'être reliés à un nouveau fichier."""
        self._media_listeners.append(listener)

    def relink(self, media: Media, new_path: Path) -> list[Media]:
        """Relie un média introuvable à `new_path`, puis cherche les autres médias
        introuvables dans le même dossier (même nom de fichier) et les relie aussi.

        Lève MediaProbeError si le fichier est illisible ou d'un autre type que le média.
        Renvoie les médias reliés, le premier étant celui demandé.
        """
        relinked = [self._relinked_copy(media, Path(new_path))]
        for other in self._project.missing_media():
            if other.id == media.id:
                continue
            candidate = Path(new_path).parent / other.path.name
            if candidate.is_file():
                try:
                    relinked.append(self._relinked_copy(other, candidate))
                except MediaProbeError:
                    log.info("Fichier trouvé mais inutilisable pour %s : %s", other.name, candidate)

        with self._lock:
            for new in relinked:
                self._project.replace_media(new)
        log.info("Médias reliés : %s", ", ".join(m.name for m in relinked))
        for listener in self._media_listeners:
            listener(relinked)
        self.mark_dirty()
        return relinked

    @staticmethod
    def _relinked_copy(media: Media, path: Path) -> Media:
        new = probe(path)
        if type(new) is not type(media):
            expected = _KIND_NAMES.get(type(media).__name__, "le même type de média")
            raise MediaProbeError(f"{path.name} n'est pas {expected}.")
        # Même identifiant : les clips qui utilisent ce média continuent de le trouver.
        return new.model_copy(update={"id": media.id})

    def new(self) -> None:
        self._replace(Project(), path=None)

    def open(self, path: Path) -> None:
        """Ouvre un projet. Lève ProjectFileError ; le projet courant est alors conservé."""
        path = Path(path).absolute()
        try:
            project = project_file.load(path)
        except project_file.ProjectFileError:
            self.recent.remove(path)
            raise
        self.recent.add(path)
        self._replace(project, path)
        log.info("Projet ouvert : %s (%d médias)", path, len(project.media))

    def save(self) -> None:
        """Enregistre dans le fichier courant. Le projet doit déjà avoir un fichier."""
        if self._path is None:
            raise ValueError("Le projet n'a pas encore de fichier : utiliser save_as.")
        self.save_as(self._path)

    def save_as(self, path: Path) -> None:
        """Enregistre dans `path` (l'extension .makitop est ajoutée si besoin)."""
        path = Path(path).absolute()
        if path.suffix.lower() != project_file.EXTENSION:
            path = path.with_name(path.name + project_file.EXTENSION)
        with self._lock:
            if path != self._path:
                self._project.name = path.stem
            project_file.save(self._project, path)
            self._path = path
            self._dirty = False
        self.recent.add(path)
        log.info("Projet enregistré : %s", path)
        self._notify_state()

    def mark_dirty(self) -> None:
        with self._lock:
            if self._dirty:
                return
            self._dirty = True
        self._notify_state()

    def _replace(self, project: Project, path: Path | None) -> None:
        with self._lock:
            self._project = project
            self._path = path
            self._dirty = False
        for listener in self._project_listeners:
            listener(project)
        self._notify_state()

    def _notify_state(self) -> None:
        for listener in self._state_listeners:
            listener()
