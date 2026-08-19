"""Pure geometry helpers shared by the renderer.

Kept free of OpenCV so the sizing rules can be tested without a display or a
camera attached.
"""

import math


def fit_size(src_width, src_height, box_width, box_height):
    """Largest (width, height) that fits in the box at the source aspect ratio.

    The original code stretched a 4:3 webcam frame onto a 16:9 panel, which
    distorts everything the detector drew and makes side-by-side panels
    misleading. Scaling by the smaller of the two ratios preserves the aspect
    ratio instead.
    """
    if src_width <= 0 or src_height <= 0 or box_width <= 0 or box_height <= 0:
        return (0, 0)
    scale = min(box_width / src_width, box_height / src_height)
    return (max(1, int(src_width * scale)), max(1, int(src_height * scale)))


def centre_offset(inner_width, inner_height, box_width, box_height):
    """Top-left offset that centres an inner rectangle inside a box."""
    return (
        max(0, (box_width - inner_width) // 2),
        max(0, (box_height - inner_height) // 2),
    )


def grid_shape(count):
    """Rows and columns for ``count`` panels, kept as square as possible."""
    if count <= 0:
        return (0, 0)
    columns = math.ceil(math.sqrt(count))
    rows = math.ceil(count / columns)
    return (rows, columns)


def clamp_text_origin(x, y, text_height=12, margin=4):
    """Keep a putText baseline inside the frame.

    OpenCV takes the *baseline* as the text origin, so an origin of (0, 0)
    renders the glyphs above the top edge where they cannot be seen.
    """
    return (max(margin, int(x)), max(text_height + margin, int(y)))
