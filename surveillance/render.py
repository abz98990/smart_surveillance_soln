"""Drawing detections onto frames, and tiling frames for a multi-camera view."""

import time

import cv2
import numpy as np

from surveillance.geometry import centre_offset, clamp_text_origin, fit_size, grid_shape

FONT = cv2.FONT_HERSHEY_SIMPLEX
DEFAULT_COLOUR = (200, 200, 200)
SEVERITY_COLOURS = {"critical": (0, 0, 235), "warning": (0, 165, 235)}


def _label(frame, text, x, y, colour, scale=0.5, thickness=1):
    """Text on a filled plate, so it stays readable over any background."""
    (width, height), baseline = cv2.getTextSize(text, FONT, scale, thickness)
    x, y = clamp_text_origin(x, y, text_height=height + baseline)
    cv2.rectangle(
        frame,
        (x - 2, y - height - baseline - 2),
        (x + width + 2, y + 2),
        colour,
        cv2.FILLED,
    )
    cv2.putText(frame, text, (x, y - baseline + 1), FONT, scale, (255, 255, 255),
                thickness, cv2.LINE_AA)


def annotate(frame, detections, colours, copy=True):
    # copy defaults to True: sharing one buffer between detectors is how the
    # old quad view ended up with every panel showing the previous one's boxes.
    canvas = frame.copy() if copy else frame
    for detection in detections:
        colour = tuple(colours.get(detection.detector, DEFAULT_COLOUR))
        x1, y1, x2, y2 = detection.box
        cv2.rectangle(canvas, (x1, y1), (x2, y2), colour, 2)
        _label(
            canvas,
            "{} {:.0f}%".format(detection.label, detection.confidence * 100),
            x1,
            y1 - 4,
            colour,
        )
    return canvas


def stamp_status(frame, camera_name, fps, alert=None):
    _label(frame, "{}  |  {:.1f} fps".format(camera_name, fps), 8, 22,
           (60, 60, 60), scale=0.55)
    _label(frame, time.strftime("%Y-%m-%d %H:%M:%S"), 8, frame.shape[0] - 8,
           (60, 60, 60), scale=0.45)

    if alert is not None:
        colour = SEVERITY_COLOURS.get(alert.severity, (0, 140, 235))
        height, width = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (width - 1, height - 1), colour, 6)
        _label(frame, "{}  {}".format(alert.title, alert.detail),
               8, 48, colour, scale=0.6, thickness=2)
    return frame


def fit_into(frame, box_width, box_height, background=0):
    """Letterbox into a box rather than stretching to it."""
    height, width = frame.shape[:2]
    new_width, new_height = fit_size(width, height, box_width, box_height)
    resized = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

    canvas = np.full((box_height, box_width, 3), background, dtype=np.uint8)
    x, y = centre_offset(new_width, new_height, box_width, box_height)
    canvas[y:y + new_height, x:x + new_width] = resized
    return canvas


def compose_grid(frames, width, height, background=18):
    canvas = np.full((height, width, 3), background, dtype=np.uint8)
    if not frames:
        return canvas

    rows, columns = grid_shape(len(frames))
    cell_width, cell_height = width // columns, height // rows

    for index, frame in enumerate(frames):
        row, column = divmod(index, columns)
        tile = fit_into(frame, cell_width, cell_height, background)
        y, x = row * cell_height, column * cell_width
        # Slice by the tile's shape - a fixed width//2 does not always add back
        # up to width, and the mismatch raises.
        canvas[y:y + tile.shape[0], x:x + tile.shape[1]] = tile
    return canvas


def encode_jpeg(frame, quality=75):
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return buffer.tobytes() if ok else None
