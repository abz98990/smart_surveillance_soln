"""Sizing helpers, kept free of OpenCV so they can be tested anywhere."""

import math


def fit_size(src_width, src_height, box_width, box_height):
    """Largest size that fits the box without changing the aspect ratio."""
    if src_width <= 0 or src_height <= 0 or box_width <= 0 or box_height <= 0:
        return (0, 0)
    scale = min(box_width / src_width, box_height / src_height)
    return (max(1, int(src_width * scale)), max(1, int(src_height * scale)))


def centre_offset(inner_width, inner_height, box_width, box_height):
    return (
        max(0, (box_width - inner_width) // 2),
        max(0, (box_height - inner_height) // 2),
    )


def grid_shape(count):
    if count <= 0:
        return (0, 0)
    columns = math.ceil(math.sqrt(count))
    rows = math.ceil(count / columns)
    return (rows, columns)


def clamp_text_origin(x, y, text_height=12, margin=4):
    """OpenCV takes the text baseline as the origin, so (0, 0) renders the
    glyphs above the frame where nobody sees them."""
    return (max(margin, int(x)), max(text_height + margin, int(y)))
