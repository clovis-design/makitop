import cv2
import dearpygui.dearpygui as dpg
import numpy as np


TAG = "preview_panel"

VIDEO_TEXTURE_TAG = "video_texture"
VIDEO_IMAGE_TAG = "video_image"
TIME_TEXT_TAG = "preview_time"

PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 360


def create_video_texture() -> None:
    # Dear PyGui attend 4 valeurs par pixel :
    # Rouge, Vert, Bleu, Alpha
    empty_texture = [0.0] * (
        PREVIEW_WIDTH
        * PREVIEW_HEIGHT
        * 4
    )

    with dpg.texture_registry():
        dpg.add_dynamic_texture(
            width=PREVIEW_WIDTH,
            height=PREVIEW_HEIGHT,
            default_value=empty_texture,
            tag=VIDEO_TEXTURE_TAG,
        )


def update_frame(frame: np.ndarray) -> None:
    # La frame venant de PyAV est en RGB :
    # shape = (hauteur, largeur, 3)

    resized_frame = cv2.resize(
        frame,
        (PREVIEW_WIDTH, PREVIEW_HEIGHT),
    )

    # Conversion 0-255 vers 0.0-1.0
    rgb = resized_frame.astype(np.float32) / 255.0

    # Dear PyGui veut du RGBA.
    # On crée donc un canal alpha rempli à 1.0
    # 1.0 = complètement opaque.
    alpha = np.ones(
        (
            PREVIEW_HEIGHT,
            PREVIEW_WIDTH,
            1,
        ),
        dtype=np.float32,
    )

    # RGB + Alpha
    rgba = np.concatenate(
        (rgb, alpha),
        axis=2,
    )

    # Transformation en tableau 1D pour Dear PyGui
    texture_data = rgba.flatten()

    dpg.set_value(
        VIDEO_TEXTURE_TAG,
        texture_data,
    )
    
def update_time(seconds: float) -> None:
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    text = f"{minutes:02d}:{remaining_seconds:02d}"

    dpg.set_value(
        TIME_TEXT_TAG,
        text,
    )


def create(
    on_play=None,
    on_pause=None,
    on_stop=None,
) -> None:

    with dpg.child_window(tag=TAG, border=True):

        dpg.add_text("Preview")

        dpg.add_separator()

        dpg.add_image(
            VIDEO_TEXTURE_TAG,
            tag=VIDEO_IMAGE_TAG,
        )

        dpg.add_separator()

        with dpg.group(horizontal=True):

            dpg.add_button(
                label="Play",
                callback=on_play,
            )

            dpg.add_button(
                label="Pause",
                callback=on_pause,
            )

            dpg.add_button(
                label="Stop",
                callback=on_stop,
            )

        dpg.add_text(
            "00:00",
            tag=TIME_TEXT_TAG,
        )