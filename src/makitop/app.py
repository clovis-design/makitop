"""Point d'entrée : crée le contexte Dear PyGui, assemble les composants et lance la boucle."""

import logging
from concurrent.futures import Executor, ThreadPoolExecutor

import dearpygui.dearpygui as dpg

from makitop import __version__
from makitop.application.composition import CompositionEditor
from makitop.application.media import MediaImporter
from makitop.application.projects import ProjectSession
from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.model.media import Media
from makitop.storage.recent import RecentProjects, config_dir
from makitop.ui import home, main_window, menu_bar, screens
from makitop.ui.dialogs import import_media, message, project_file
from makitop.ui.panels import media as media_panel
from makitop.ui.panels import preview, properties
from makitop.ui.panels import timeline as timeline_panel

TITLE = f"Makitop {__version__}"
DEFAULT_WIDTH = 1660
DEFAULT_HEIGHT = 800
MENU_RECENT_COUNT = 10

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s : %(message)s")
    session = ProjectSession(RecentProjects(config_dir() / "recent.json"))
    executor = ThreadPoolExecutor(thread_name_prefix="makitop")
    importer = MediaImporter(lambda: session.project, executor)
    playback_controller = TimelinePlaybackController()
    editor = CompositionEditor(session, playback_controller)

    def refresh_editor():
        preview.refresh()
        properties.refresh()
        timeline_panel.refresh()

    def composition_error(text):
        message.show("Composition", text)

    def select_media(media: Media) -> None:
        try:
            editor.preview_source(media)
        except ValueError as exc:
            composition_error(str(exc))

    def on_add_to_timeline(media: Media) -> None:
        try:
            editor.add_media(media)
        except ValueError as exc:
            composition_error(str(exc))

    def refresh_project_media() -> None:
        preview.clear()
        timeline_panel.clear()
        _show_project_media(session, executor)
        editor.selected_id = None
        editor.show_montage(0)

    def show_home() -> None:
        playback_controller.pause()
        screens.show_home()
        _refresh_title_and_projects(session)

    def editor_only(action):
        return lambda: None if screens.home_shown() else action()

    dpg.create_context()
    try:
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
            on_add_to_timeline=on_add_to_timeline,
        )
        home.create(on_new=project_file.new_project, on_open=project_file.open_dialog)
        import_media.create(on_files_selected=importer.import_files)
        preview.bind(editor, composition_error)
        properties.bind(editor, composition_error)
        timeline_panel.bind(editor, composition_error)
        editor.on_refresh = refresh_editor
        editor.show_montage(0)
        project_file.create(session)

        importer.on_failed(import_media.show_error)

        importer.on_imported(media_panel.add_media)
        importer.on_imported(lambda _: session.mark_dirty())
        session.on_project_changed(lambda project: refresh_project_media())
        session.on_project_changed(lambda project: screens.show_editor())
        session.on_media_relinked(lambda _: refresh_project_media())
        session.on_state_changed(lambda: _refresh_title_and_projects(session))

        dpg.create_viewport(
            title=TITLE,
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            min_width=1500,
            min_height=600,
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
            timeline_panel.set_playhead(0 if editor.source_mode else current_time)

            try:
                frame = playback_controller.poll()
                if frame is not None:
                    preview.update_frame(frame)
            except Exception as exc:
                log.exception("Rendu impossible")
                message.show("Lecture impossible", str(exc))

            dpg.render_dearpygui_frame()

    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        playback_controller.close()
        dpg.destroy_context()


def _show_project_media(session: ProjectSession, executor: Executor) -> None:
    media_panel.clear()
    project = session.project

    def show_all() -> None:
        for media in list(project.media):
            if session.project is not project:
                return
            try:
                media_panel.add_media(media)
            except Exception:
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
