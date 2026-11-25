"""Point d'entrée : crée le contexte Dear PyGui, assemble les composants et lance la boucle."""

import logging
import sys
from concurrent.futures import Executor, ThreadPoolExecutor

import dearpygui.dearpygui as dpg

from makitop import __version__
from makitop.application.composition import CompositionEditor
from makitop.application.media import MediaImporter
from makitop.application.projects import ProjectSession
from makitop.application.timeline_playback import TimelinePlaybackController
from makitop.model.media import Media
from makitop.storage.recent import RecentProjects, config_dir
from makitop.ui import home, main_window, menu_bar, screens, shortcuts
from makitop.ui.assets.style import LOGO
from makitop.ui.dialogs import import_media, message, project_file
from makitop.ui.dialogs.export_video import ExportDialog
from makitop.ui.panels import effects as effects_panel
from makitop.ui.panels import media as media_panel
from makitop.ui.panels import preview, properties, text_presets
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
            editor.add_media(media)
        except ValueError as exc:
            composition_error(str(exc))

    def on_add_to_timeline(media: Media) -> None:
        try:
            editor.add_media(media)
        except ValueError as exc:
            composition_error(str(exc))

    def apply_effect(kind: str) -> None:
        try:
            editor.add_effect(kind)
        except ValueError as exc:
            composition_error(str(exc))

    def on_add_text(preset: str) -> None:
        try:
            editor.add_text(preset)
        except ValueError as exc:
            composition_error(str(exc))

    def refresh_project_media() -> None:
        preview.clear()
        timeline_panel.clear()
        _show_project_media(session, executor)
        editor.selected_id = None
        # On reprend là où le projet a été laissé (position enregistrée avec le projet).
        editor.show_montage(session.project.view.playhead)

    def show_home() -> None:
        playback_controller.pause()
        screens.show_home()
        _refresh_title_and_projects(session)

    def editor_only(action):
        return lambda: None if screens.home_shown() else action()

    dpg.create_context()
    export_dialog = None
    try:
        dpg.configure_app(manual_callback_management=True)
        export_dialog = ExportDialog(session, executor)
        main_window.build(
            actions={
                menu_bar.NEW_PROJECT: project_file.new_project,
                menu_bar.OPEN_PROJECT: project_file.open_dialog,
                menu_bar.SAVE_PROJECT: editor_only(project_file.save),
                menu_bar.SAVE_PROJECT_AS: editor_only(project_file.save_dialog),
                menu_bar.IMPORT_MEDIA: editor_only(import_media.open_dialog),
                menu_bar.EXPORT_VIDEO: editor_only(export_dialog.open),
                menu_bar.CLOSE_PROJECT: editor_only(lambda: project_file.close_project(show_home)),
                menu_bar.QUIT: project_file.quit_app,
            },
            playback_controller=playback_controller,
            on_media_selected=select_media,
            on_add_to_timeline=on_add_to_timeline,
            block_shortcuts=export_dialog.blocks_editor,
            on_add_text=on_add_text,
        )
        home.create(on_new=project_file.new_project, on_open=project_file.open_dialog)
        import_media.create(on_files_selected=importer.import_files)

        _SEEK_STEP = 5.0

        def _on_playback_key(sender, key: int) -> None:
            if (screens.home_shown() or export_dialog.blocks_editor()
                    or shortcuts.text_input_active()
                    or dpg.is_item_active(properties.TEXT_CONTENT)):
                return
            ctrl = dpg.is_key_down(dpg.mvKey_LControl) or dpg.is_key_down(dpg.mvKey_RControl)
            if key == dpg.mvKey_F and not shortcuts.ctrl_down():
                main_window.toggle_fullscreen()
            elif key == dpg.mvKey_Escape and main_window.is_fullscreen():
                main_window.set_fullscreen(False)
            elif key == dpg.mvKey_Spacebar and not ctrl:
                if playback_controller.is_playing():
                    playback_controller.pause()
                else:
                    playback_controller.play()
            elif key == dpg.mvKey_Left and not ctrl:
                playback_controller.seek(max(0.0, playback_controller.current_time() - _SEEK_STEP))
            elif key == dpg.mvKey_Right and not ctrl:
                playback_controller.seek(playback_controller.current_time() + _SEEK_STEP)
            elif key == dpg.mvKey_Home and not ctrl:
                playback_controller.seek(0.0)
            elif key == dpg.mvKey_Delete and not ctrl:
                timeline_panel.delete_selected()
            elif ctrl and key == dpg.mvKey_K:
                timeline_panel.toggle_keyframes()
            elif ctrl and key == dpg.mvKey_B:
                timeline_panel.split_at_playhead()
            elif ctrl and key == dpg.mvKey_Z:
                timeline_panel.undo()
            elif ctrl and key == dpg.mvKey_Y:
                timeline_panel.redo()
            elif ctrl and key == dpg.mvKey_D:
                timeline_panel.duplicate_selected()
            elif ctrl and key == dpg.mvKey_C:
                timeline_panel.copy_selected()
            elif ctrl and key == dpg.mvKey_X:
                timeline_panel.cut_selected()
            elif ctrl and key == dpg.mvKey_V:
                timeline_panel.paste_clip()
            elif ctrl and key in (dpg.mvKey_Subtract, dpg.mvKey_Minus):
                timeline_panel.zoom_out()
            elif ctrl and key == dpg.mvKey_Add:
                timeline_panel.zoom_in()

        with dpg.handler_registry():
            dpg.add_key_press_handler(callback=_on_playback_key)

        preview.bind(editor, composition_error)
        preview.bind_export(editor_only(export_dialog.open))
        properties.bind(editor, composition_error)
        timeline_panel.bind(editor, composition_error)
        effects_panel.bind(apply_effect)
        editor.on_refresh = refresh_editor
        editor.show_montage(0)
        project_file.create(session)

        importer.on_failed(import_media.show_error)
        importer.on_imported(media_panel.add_media)

        def _on_media_deleted(media: Media) -> None:
            project = session.project
            project.media = [m for m in project.media if m.id != media.id]
            for clip in [c for c in project.timeline.clips if hasattr(c, "media") and c.media.id == media.id]:
                project.timeline.remove_clip(clip.id)
                if editor.selected_id == clip.id:
                    editor.selected_id = None
            session.mark_dirty()
            refresh_project_media()

        media_panel.bind_delete_media(_on_media_deleted)
        importer.on_imported(media_panel.add_media)
        importer.on_imported(lambda _: session.mark_dirty())
        session.on_project_changed(lambda project: refresh_project_media())
        session.on_project_changed(lambda project: screens.show_editor())
        session.on_media_relinked(lambda _: refresh_project_media())
        session.on_state_changed(lambda: _refresh_title_and_projects(session))

        icon = _window_icon()
        dpg.create_viewport(
            title=TITLE,
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            min_width=1500,
            min_height=600,
            disable_close=True,
            small_icon=icon,
            large_icon=icon,
        )
        dpg.set_exit_callback(project_file.quit_app)
        dpg.set_viewport_resize_callback(lambda: screens.resize())
        dpg.setup_dearpygui()
        dpg.show_viewport()
        _poll_error_shown = False
        show_home()
        while dpg.is_dearpygui_running():
            dpg.run_callbacks(dpg.get_callback_queue())

            current_time = playback_controller.current_time()
            editor.sync_playhead()
            preview.update_time(current_time)
            properties.tick(current_time)
            timeline_panel.set_playhead(current_time)

            try:
                frame = playback_controller.poll()
                if frame is not None:
                    preview.update_frame(frame)
                _poll_error_shown = False
            except Exception as exc:
                log.exception("Rendu impossible")
                if not _poll_error_shown:
                    _poll_error_shown = True
                    message.show("Lecture impossible", str(exc))

            if not export_dialog.blocks_editor():
                timeline_panel.tick()
                media_panel.tick()
                text_presets.tick()
            export_dialog.tick()
            dpg.render_dearpygui_frame()

    finally:
        if export_dialog is not None:
            export_dialog.close()
        executor.shutdown(wait=True, cancel_futures=True)
        playback_controller.close()
        dpg.destroy_context()


def _window_icon() -> str:
    """Chemin de l'icône de la fenêtre ; "" garde l'icône par défaut.

    Windows n'accepte qu'un .ico : logo.png est converti. Linux et macOS lisent le PNG
    directement (et ne savent pas lire un .ico).
    """
    if not LOGO.exists():
        log.warning("Logo introuvable : %s", LOGO)
        return ""
    if sys.platform != "win32":
        return str(LOGO)
    ico = config_dir() / "makitop.ico"
    try:
        from PIL import Image

        ico.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(LOGO) as image:
            image.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    except Exception:
        log.exception("Icône de fenêtre impossible à créer")
        return ""
    return str(ico)


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
