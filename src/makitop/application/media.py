"""Import de médias : analyse des fichiers en arrière-plan et ajout au projet.

Les écouteurs (`on_imported`, `on_failed`) sont appelés depuis un thread de travail :
ils ne doivent faire que des opérations thread-safe (Dear PyGui 2.3+ l'est).
"""

import logging
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import Executor, Future
from pathlib import Path

from makitop.media.probe import MediaProbeError, probe
from makitop.model.media import Media
from makitop.model.project import Project

log = logging.getLogger(__name__)

ImportedListener = Callable[[Media], None]
FailedListener = Callable[[Path, str], None]


class MediaImporter:
    def __init__(self, project: Project, executor: Executor) -> None:
        self._project = project
        self._executor = executor
        self._lock = threading.Lock()
        self._imported_listeners: list[ImportedListener] = []
        self._failed_listeners: list[FailedListener] = []

    def on_imported(self, listener: ImportedListener) -> None:
        """Appelé pour chaque média ajouté au projet (utile pour l'affichage des médias)."""
        self._imported_listeners.append(listener)

    def on_failed(self, listener: FailedListener) -> None:
        """Appelé avec le chemin et un message lisible quand un fichier ne peut pas être importé."""
        self._failed_listeners.append(listener)

    def import_files(self, paths: Iterable[Path]) -> list[Future[Media | None]]:
        """Lance l'import de chaque fichier sans bloquer l'appelant."""
        return [self._executor.submit(self._import_one, Path(p)) for p in paths]

    def _import_one(self, path: Path) -> Media | None:
        try:
            if self._project.find_media(path) is not None:
                raise MediaProbeError(f"Déjà importé : {path.name}")
            media = probe(path)
            with self._lock:
                self._project.add_media(media)
        except (MediaProbeError, ValueError) as error:
            self._notify_failed(path, str(error))
            return None
        except Exception:
            log.exception("Erreur inattendue pendant l'import de %s", path)
            self._notify_failed(path, f"Erreur inattendue : {path.name}")
            return None

        log.info("Média importé : %s (%s)", media.name, media.kind)
        for listener in self._imported_listeners:
            listener(media)
        return media

    def _notify_failed(self, path: Path, message: str) -> None:
        log.warning("Import impossible : %s", message)
        for listener in self._failed_listeners:
            listener(path, message)
