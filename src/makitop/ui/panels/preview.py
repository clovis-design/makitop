import cv2
import dearpygui.dearpygui as dpg
import numpy as np


TAG = "preview_panel"

VIDEO_TEXTURE_TAG = "video_texture"
VIDEO_IMAGE_TAG = "video_image"

PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 360


def create_video_texture() -> None:
    empty_texture = [0.0] * (
        PREVIEW_WIDTH
        * PREVIEW_HEIGHT
        * 3
    )

    with dpg.texture_registry():
        dpg.add_dynamic_texture(
            width=PREVIEW_WIDTH,
            height=PREVIEW_HEIGHT,
            default_value=empty_texture,
            tag=VIDEO_TEXTURE_TAG,
        )


def update_frame(frame: np.ndarray) -> None:
    resized_frame = cv2.resize(
        frame,
        (PREVIEW_WIDTH, PREVIEW_HEIGHT),
    )

    texture_data = resized_frame.astype(np.float32) / 255.0

    texture_data = texture_data.flatten()

    dpg.set_value(
        VIDEO_TEXTURE_TAG,
        texture_data,
    )


def create() -> None:
    with dpg.child_window(
        tag=TAG,
        border=True,
    ):
        dpg.add_text("Preview")

        dpg.add_separator()

        dpg.add_image(
            VIDEO_TEXTURE_TAG,
            tag=VIDEO_IMAGE_TAG,
        )