"""Point d'entrée : crée le contexte Dear PyGui, assemble les composants et lance la boucle."""

import logging
from concurrent.futures import Executor, ThreadPoolExecutor

import dearpygui.dearpygui as dpg

from makitop import __version__
from makitop.application.media import MediaImporter
from makitop.application.projects import ProjectSession
from makitop.storage.recent import RecentProjects, config_dir
from makitop.application.playback import PlaybackController
from makitop.engine.decoder import MediaDecoder
from makitop.engine.render import Renderer
from makitop.playback.player import Player
from makitop.ui import main_window, menu_bar
from makitop.ui.dialogs import import_media, project_file
from makitop.ui.panels import media as media_panel
from makitop.ui.panels import preview

TITLE = f"Makitop {__version__}"
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 800

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s : %(message)s")
    session = ProjectSession(RecentProjects(config_dir() / "recent.json"))
    executor = ThreadPoolExecutor(thread_name_prefix="makitop")
    importer = MediaImporter(lambda: session.project, executor)

    dpg.create_context()
    try:
        main_window.build(
            actions={
                menu_bar.NEW_PROJECT: project_file.new_project,
                menu_bar.OPEN_PROJECT: project_file.open_dialog,
                menu_bar.SAVE_PROJECT: project_file.save,
                menu_bar.SAVE_PROJECT_AS: project_file.save_dialog,
                menu_bar.IMPORT_MEDIA: import_media.open_dialog,
                menu_bar.QUIT: project_file.quit_app,
            }
        )
        import_media.create(on_files_selected=importer.import_files)
        project_file.create(session)

        importer.on_failed(import_media.show_error)

        decoder = MediaDecoder()
        decoder.open("test.mp4")
        renderer = Renderer(decoder)
        player = Player(renderer)
        playback_controller = PlaybackController(player)

        main_window.build(playback_controller)

        preview.initFinalTime(decoder.get_duration())


        frame = decoder.get_first_frame()

        preview.update_frame(frame)
        importer.on_imported(media_panel.add_media)
        importer.on_imported(lambda _: session.mark_dirty())
        session.on_project_changed(lambda project: _show_project_media(session, executor))
        session.on_media_relinked(lambda _: _show_project_media(session, executor))
        session.on_state_changed(lambda: _refresh_title_and_recent(session))

        dpg.create_viewport(
            title=TITLE,
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            min_width=800,
            min_height=500,
            # La croix ne ferme pas directement : on demande d'abord d'enregistrer.
            disable_close=True,
        )
        dpg.set_exit_callback(project_file.quit_app)
        dpg.set_viewport_resize_callback(lambda: main_window.resize(*_viewport_client_size()))
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window(main_window.ROOT, True)
        main_window.resize(*_viewport_client_size())
        while dpg.is_dearpygui_running():

            current_time = playback_controller.current_time()

            preview.update_time(current_time)

            frame = playback_controller.current_frame()

            if frame is not None:
                preview.update_frame(frame)

    
        _refresh_title_and_recent(session)

        dpg.render_dearpygui_frame()

    finally:
        # On attend les analyses en cours : elles peuvent encore appeler Dear PyGui.
        executor.shutdown(wait=True, cancel_futures=True)
        dpg.destroy_context()


def _show_project_media(session: ProjectSession, executor: Executor) -> None:
    media_panel.clear()
    project = session.project

    def show_all() -> None:
        # Miniatures calculées en arrière-plan, dans l'ordre du projet ; on s'arrête si
        # un autre projet est ouvert entre-temps.
        for media in list(project.media):
            if session.project is not project:
                return
            try:
                media_panel.add_media(media)
            except Exception:
                # Sinon l'erreur disparaît silencieusement dans le thread de travail.
                log.exception("Affichage impossible du média %s", media.path)

    executor.submit(show_all)


def _reopen_last_project(session: ProjectSession) -> None:
    last = session.recent.last()
    if last is not None:
        project_file.open_path(last)


def _refresh_title_and_recent(session: ProjectSession) -> None:
    dpg.set_viewport_title(f"{session.title} - {TITLE}")
    menu_bar.set_recent_projects(session.recent.paths(), project_file.open_recent)


def _viewport_client_size() -> tuple[int, int]:
    return dpg.get_viewport_client_width(), dpg.get_viewport_client_height()


if __name__ == "__main__":
    main()
