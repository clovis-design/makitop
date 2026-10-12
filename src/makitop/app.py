"""Point d'entrée : crée le contexte Dear PyGui, assemble les composants et lance la boucle."""

import logging
from concurrent.futures import Executor, ThreadPoolExecutor

import dearpygui.dearpygui as dpg

from makitop import __version__
from makitop.application.media import MediaImporter
from makitop.application.projects import ProjectSession
from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.model.media import Media, MediaKind
from makitop.model.project import Project
from makitop.model.timeline import Clip, Timeline
from makitop.storage.recent import RecentProjects, config_dir
from makitop.ui import home, main_window, menu_bar, screens
from makitop.ui.dialogs import import_media, message, project_file
from makitop.ui.panels import media as media_panel
from makitop.ui.panels import preview, timeline

TITLE = f"Makitop {__version__}"
DEFAULT_WIDTH = 1660
DEFAULT_HEIGHT = 800
# Le sous-menu « Projets récents » reste court ; la page d'accueil liste tous les projets.
MENU_RECENT_COUNT = 10

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s : %(message)s")
    session = ProjectSession(RecentProjects(config_dir() / "recent.json"))
    executor = ThreadPoolExecutor(thread_name_prefix="makitop")
    importer = MediaImporter(lambda: session.project, executor)
    playback_controller = TimelinePlaybackController()
    selected_media = None
    viewing_montage = True

    def show_montage(position=0.0):
        nonlocal viewing_montage
        viewing_montage = True
        playback_controller.set_project(session.project, position)
        preview.clear()
        preview.initFinalTime(playback_controller.duration)
        dpg.set_value("preview_mode", "Montage — vidéo sans audio")

    def edit(action):
        position = playback_controller.current_time() if viewing_montage else 0.0
        try:
            action()
        except (ValueError, StopIteration) as exc:
            message.show("Montage", str(exc))
            return
        session.mark_dirty()
        timeline.refresh(session.project)
        show_montage(position)

    def add_portion(source_in, source_out):
        def action():
            if selected_media is None:
                raise ValueError("Sélectionnez une vidéo dans les médias.")
            if source_out > (selected_media.duration or 0):
                raise ValueError("La sortie dépasse la durée de la vidéo.")
            session.project.timeline.append(selected_media.id, source_in, source_out)
        edit(action)

    def split_clip():
        if not viewing_montage:
            show_montage()
            return
        fps = session.project.timeline.fps
        position = round(playback_controller.current_time() * fps) / fps
        edit(lambda: session.project.timeline.split(position))

    def remove_clip():
        index = timeline.selected_index()
        if index is not None:
            edit(lambda: session.project.timeline.remove(session.project.timeline.clips[index].id))

    def seek_montage(position):
        if not viewing_montage:
            show_montage(position)
        else:
            playback_controller.seek(position)

    def select_media(media: Media) -> None:
        nonlocal selected_media, viewing_montage
        if media.kind is not MediaKind.VIDEO:
            message.show("Lecteur vidéo", "Sélectionnez un média vidéo pour le lire.")
            return
        if not media.duration or media.duration <= 0:
            message.show("Lecture impossible", "Cette vidéo n'a pas de durée exploitable.")
            return
        selected_media = media
        viewing_montage = False
        timeline.select_media(media)
        playback_controller.set_project(Project(
            media=[media], timeline=Timeline([Clip(media.id, 0, media.duration, 0)])
        ))
        preview.clear()
        preview.initFinalTime(media.duration)
        dpg.set_value("preview_mode", "Source — vidéo sans audio")

    def refresh_project_media() -> None:
        nonlocal selected_media
        selected_media = None
        dpg.set_value("timeline_selection", "Aucune vidéo sélectionnée")
        timeline.refresh(session.project)
        show_montage()
        _show_project_media(session, executor)

    def show_home() -> None:
        screens.show_home()
        _refresh_title_and_projects(session)

    def editor_only(action):
        # Sur la page d'accueil, il n'y a pas de projet à enregistrer ni où importer.
        return lambda: None if screens.home_shown() else action()

    dpg.create_context()
    try:
        # Les callbacks modifient le modèle sur le thread UI ; le worker lit une copie.
        dpg.configure_app(manual_callback_management=True)
        main_window.build(
            actions={
                menu_bar.NEW_PROJECT: project_file.new_project,
                menu_bar.OPEN_PROJECT: project_file.open_dialog,
                menu_bar.SAVE_PROJECT: editor_only(project_file.save),
                menu_bar.SAVE_PROJECT_AS: editor_only(project_file.save_dialog),
                menu_bar.IMPORT_MEDIA: editor_only(import_media.open_dialog),
                menu_bar.CLOSE_PROJECT: editor_only(lambda: project_file.close_project(show_home)),
                menu_bar.QUIT: project_file.quit_app,
            },
            playback_controller=playback_controller,
            on_media_selected=select_media,
        )
        home.create(on_new=project_file.new_project, on_open=project_file.open_dialog)
        import_media.create(on_files_selected=importer.import_files)
        timeline.bind(add_portion, show_montage, seek_montage, split_clip, remove_clip)
        show_montage()
        project_file.create(session)

        importer.on_failed(import_media.show_error)

        importer.on_imported(media_panel.add_media)
        importer.on_imported(lambda _: session.mark_dirty())
        session.on_project_changed(lambda project: refresh_project_media())
        # Créer ou ouvrir un projet fait passer de l'accueil à l'éditeur.
        session.on_project_changed(lambda project: screens.show_editor())
        session.on_media_relinked(lambda _: refresh_project_media())
        session.on_state_changed(lambda: _refresh_title_and_projects(session))

        dpg.create_viewport(
            title=TITLE,
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            min_width=1500,
            min_height=600,
            # La croix ne ferme pas directement : on demande d'abord d'enregistrer.
            disable_close=True,
        )
        dpg.set_exit_callback(project_file.quit_app)
        dpg.set_viewport_resize_callback(lambda: screens.resize())
        dpg.setup_dearpygui()
        dpg.show_viewport()
        show_home()
        while dpg.is_dearpygui_running():
            dpg.run_callbacks(dpg.get_callback_queue())

            current_time = playback_controller.current_time()

            preview.update_time(current_time)

            if viewing_montage:
                timeline.update_time(current_time)
            try:
                frame = playback_controller.poll()
                if frame is not None:
                    preview.update_frame(frame)
            except Exception as exc:
                log.exception("Rendu du montage impossible")
                message.show("Lecture impossible", str(exc))

            dpg.render_dearpygui_frame()

    finally:
        # On attend les analyses en cours : elles peuvent encore appeler Dear PyGui.
        executor.shutdown(wait=True, cancel_futures=True)
        playback_controller.close()
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


def _refresh_title_and_projects(session: ProjectSession) -> None:
    on_home = screens.home_shown()
    dpg.set_viewport_title(TITLE if on_home else f"{session.title} - {TITLE}")
    projects = session.recent.entries()
    menu_bar.set_recent_projects(
        [p.path for p in projects[:MENU_RECENT_COUNT]], project_file.open_recent
    )
    home.set_projects(projects, project_file.open_path)


if __name__ == "__main__":
    main()
