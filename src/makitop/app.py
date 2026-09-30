"""Point d'entrée : crée le contexte Dear PyGui, assemble les composants et lance la boucle."""

import logging
from concurrent.futures import ThreadPoolExecutor

import dearpygui.dearpygui as dpg

from makitop import __version__
from makitop.application.media import MediaImporter
from makitop.model.project import Project
from makitop.application.playback import PlaybackController
from makitop.engine.decoder import MediaDecoder
from makitop.engine.render import Renderer
from makitop.playback.player import Player
from makitop.ui import main_window, menu_bar
from makitop.ui.dialogs import import_media
from makitop.ui.panels import preview

TITLE = f"Makitop {__version__}"
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 800


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s : %(message)s")
    project = Project()
    executor = ThreadPoolExecutor(thread_name_prefix="makitop")
    importer = MediaImporter(project, executor)

    dpg.create_context()
    try:
        main_window.build(actions={menu_bar.IMPORT_MEDIA: import_media.open_dialog})
        import_media.create(on_files_selected=importer.import_files)
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
        
        dpg.create_viewport(
            title=TITLE,
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            min_width=800,
            min_height=500,
        )
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

            dpg.render_dearpygui_frame()

    finally:
        # On attend les analyses en cours : elles peuvent encore appeler Dear PyGui.
        executor.shutdown(wait=True, cancel_futures=True)
        dpg.destroy_context()


def _viewport_client_size() -> tuple[int, int]:
    return dpg.get_viewport_client_width(), dpg.get_viewport_client_height()


if __name__ == "__main__":
    main()
