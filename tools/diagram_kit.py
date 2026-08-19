"""A tiny drawing toolkit for the UML figures.

The diagrams are defined once as a display list and rendered twice: to SVG,
which stays editable, and to PNG, which is what goes into the report. Keeping
one source removes the drift that let five spelling mistakes survive inside the
previous diagram images, where no spell-checker could reach them.

Only Pillow is required.
"""

import html
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- palette
INK = "#1F2933"
LINE = "#3E4C59"
MUTED = "#7B8794"
WHITE = "#FFFFFF"
BLUE = "#CFE3F5"
BLUE_DARK = "#2C6E9B"
SAND = "#FBE7D2"
GREEN = "#D6EBDD"
GREY = "#EEF1F4"
RED = "#F9DAD7"

FONT_DIR = Path("C:/Windows/Fonts")
FONT_FILES = {
    "regular": ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"],
    "bold": ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "italic": ["segoeuii.ttf", "ariali.ttf", "DejaVuSans-Oblique.ttf"],
}
SVG_FAMILY = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

_font_cache = {}


def font(size, weight="regular"):
    key = (size, weight)
    if key not in _font_cache:
        for name in FONT_FILES[weight]:
            path = FONT_DIR / name
            if path.exists():
                _font_cache[key] = ImageFont.truetype(str(path), size)
                break
        else:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


class Canvas:
    """Collects primitives, then renders them to SVG and PNG."""

    def __init__(self, width, height, background=WHITE):
        self.width = width
        self.height = height
        self.background = background
        self.items = []

    # -- primitives ------------------------------------------------------
    def rect(self, x, y, w, h, fill=WHITE, stroke=LINE, width=2, radius=0,
             dash=None):
        self.items.append(("rect", dict(x=x, y=y, w=w, h=h, fill=fill,
                                        stroke=stroke, width=width,
                                        radius=radius, dash=dash)))
        return (x, y, w, h)

    def ellipse(self, cx, cy, rx, ry, fill=BLUE, stroke=LINE, width=2):
        self.items.append(("ellipse", dict(cx=cx, cy=cy, rx=rx, ry=ry,
                                           fill=fill, stroke=stroke, width=width)))

    def line(self, points, stroke=LINE, width=2, dash=None, arrow=None,
             start_arrow=None):
        """``arrow`` is None, 'open' (association) or 'filled' (dependency)."""
        self.items.append(("line", dict(points=list(points), stroke=stroke,
                                        width=width, dash=dash, arrow=arrow,
                                        start_arrow=start_arrow)))

    def text(self, x, y, content, size=15, weight="regular", fill=INK,
             anchor="middle"):
        """``y`` is the vertical centre of the line."""
        self.items.append(("text", dict(x=x, y=y, content=content, size=size,
                                        weight=weight, fill=fill, anchor=anchor)))

    def lines_of_text(self, cx, cy, rows, size=15, weight="regular", fill=INK,
                      leading=None, anchor="middle"):
        leading = leading or size + 5
        total = leading * (len(rows) - 1)
        for index, row in enumerate(rows):
            self.text(cx, cy - total / 2 + index * leading, row,
                      size=size, weight=weight, fill=fill, anchor=anchor)

    # -- composite shapes -------------------------------------------------
    def box(self, x, y, w, h, rows, fill=WHITE, stroke=LINE, radius=0,
            size=15, weight="regular", dash=None):
        self.rect(x, y, w, h, fill=fill, stroke=stroke, radius=radius, dash=dash)
        self.lines_of_text(x + w / 2, y + h / 2, rows, size=size, weight=weight)
        return (x, y, w, h)

    def use_case(self, cx, cy, rows, rx=95, ry=48, fill=BLUE):
        self.ellipse(cx, cy, rx, ry, fill=fill)
        self.lines_of_text(cx, cy, rows, size=15)

    def actor(self, cx, cy, label, scale=1.0):
        """Stick figure with its label below. ``cy`` is the head centre."""
        r = 15 * scale
        self.ellipse(cx, cy, r, r, fill=WHITE, stroke=LINE, width=2)
        self.line([(cx, cy + r), (cx, cy + r + 42 * scale)], width=2)
        self.line([(cx - 26 * scale, cy + r + 14 * scale),
                   (cx + 26 * scale, cy + r + 14 * scale)], width=2)
        self.line([(cx, cy + r + 42 * scale),
                   (cx - 20 * scale, cy + r + 76 * scale)], width=2)
        self.line([(cx, cy + r + 42 * scale),
                   (cx + 20 * scale, cy + r + 76 * scale)], width=2)
        self.text(cx, cy + r + 96 * scale, label, size=15, weight="bold")

    def system_actor(self, cx, cy, label, w=150, h=54):
        """Non-human participant, drawn as a stereotyped box."""
        self.rect(cx - w / 2, cy - h / 2, w, h, fill=GREY)
        self.text(cx, cy - 11, "\u00ab" + "device" + "\u00bb", size=12, fill=MUTED)
        self.text(cx, cy + 10, label, size=15, weight="bold")

    def folder(self, x, y, w, h, title, rows=(), fill=WHITE):
        """UML package: a folder tab above the body."""
        tab_w, tab_h = min(w * 0.45, 190), 26
        self.rect(x, y, tab_w, tab_h, fill=fill)
        self.rect(x, y + tab_h, w, h - tab_h, fill=fill)
        self.text(x + 12, y + tab_h / 2, title, size=14, weight="bold",
                  anchor="start")
        if rows:
            self.lines_of_text(x + w / 2, y + tab_h + (h - tab_h) / 2, rows,
                               size=14)

    def component(self, x, y, w, h, rows, fill=WHITE, stereotype=True):
        """UML component: a box with the two small tabs on its left edge."""
        self.rect(x, y, w, h, fill=fill)
        for offset in (18, h - 36):
            self.rect(x - 8, y + offset, 20, 16, fill=fill)
        top = y + h / 2 - (10 if stereotype else 0)
        if stereotype:
            self.text(x + w / 2, y + 20, "\u00abcomponent\u00bb", size=11, fill=MUTED)
        self.lines_of_text(x + w / 2, top + 8, rows, size=15, weight="bold")

    def node3d(self, x, y, w, h, label, fill=GREY, depth=18, label_size=15):
        """UML deployment node: a box with an isometric top and side."""
        self.items.append(("poly", dict(
            points=[(x, y), (x + depth, y - depth), (x + w + depth, y - depth),
                    (x + w, y)], fill=fill, stroke=LINE, width=2)))
        self.items.append(("poly", dict(
            points=[(x + w, y), (x + w + depth, y - depth),
                    (x + w + depth, y + h - depth), (x + w, y + h)],
            fill=fill, stroke=LINE, width=2)))
        self.rect(x, y, w, h, fill=WHITE)
        self.text(x + w / 2, y + 20, label, size=label_size, weight="bold")

    def lollipop(self, cx, cy, label=None, r=11, side="left"):
        """Provided interface (ball)."""
        self.ellipse(cx, cy, r, r, fill=WHITE, stroke=LINE, width=2)
        if label:
            dx = -r - 8 if side == "left" else r + 8
            self.text(cx + dx, cy, label, size=12, fill=MUTED,
                      anchor="end" if side == "left" else "start")

    def fragment(self, x, y, w, h, kind, guard=None):
        """Sequence-diagram combined fragment."""
        self.rect(x, y, w, h, fill=None, stroke=LINE, width=2)
        self.rect(x, y, 92, 26, fill=WHITE, stroke=LINE, width=2)
        self.text(x + 46, y + 13, kind, size=13, weight="bold")
        if guard:
            self.text(x + 106, y + 13, guard, size=13, anchor="start")

    def title(self, text):
        self.text(self.width / 2, 34, text, size=22, weight="bold")

    # -- SVG renderer -----------------------------------------------------
    def to_svg(self):
        out = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            'viewBox="0 0 {w} {h}" font-family="{f}">'.format(
                w=self.width, h=self.height, f=SVG_FAMILY),
            '<defs>',
            '<marker id="open" viewBox="0 0 12 12" refX="11" refY="6" '
            'markerWidth="11" markerHeight="11" orient="auto-start-reverse">'
            '<path d="M1,1 L11,6 L1,11" fill="none" stroke="{}" '
            'stroke-width="1.6"/></marker>'.format(LINE),
            '<marker id="filled" viewBox="0 0 12 12" refX="11" refY="6" '
            'markerWidth="10" markerHeight="10" orient="auto-start-reverse">'
            '<path d="M1,1 L11,6 L1,11 Z" fill="{}"/></marker>'.format(LINE),
            '</defs>',
            '<rect width="100%" height="100%" fill="{}"/>'.format(self.background),
        ]

        for kind, it in self.items:
            if kind == "rect":
                fill = it["fill"] or "none"
                dash = ' stroke-dasharray="7 5"' if it["dash"] else ""
                out.append(
                    '<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
                    'fill="{fill}" stroke="{s}" stroke-width="{sw}"{d}/>'.format(
                        x=it["x"], y=it["y"], w=it["w"], h=it["h"],
                        r=it["radius"], fill=fill, s=it["stroke"],
                        sw=it["width"], d=dash))
            elif kind == "ellipse":
                out.append(
                    '<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{f}" '
                    'stroke="{s}" stroke-width="{sw}"/>'.format(
                        cx=it["cx"], cy=it["cy"], rx=it["rx"], ry=it["ry"],
                        f=it["fill"], s=it["stroke"], sw=it["width"]))
            elif kind == "poly":
                points = " ".join("{},{}".format(*p) for p in it["points"])
                out.append(
                    '<polygon points="{p}" fill="{f}" stroke="{s}" '
                    'stroke-width="{sw}"/>'.format(
                        p=points, f=it["fill"], s=it["stroke"], sw=it["width"]))
            elif kind == "line":
                points = " ".join("{},{}".format(*p) for p in it["points"])
                dash = ' stroke-dasharray="7 5"' if it["dash"] else ""
                marker = ""
                if it["arrow"]:
                    marker += ' marker-end="url(#{})"'.format(it["arrow"])
                if it["start_arrow"]:
                    marker += ' marker-start="url(#{})"'.format(it["start_arrow"])
                out.append(
                    '<polyline points="{p}" fill="none" stroke="{s}" '
                    'stroke-width="{sw}" stroke-linejoin="round"{d}{m}/>'.format(
                        p=points, s=it["stroke"], sw=it["width"], d=dash, m=marker))
            elif kind == "text":
                anchor = {"middle": "middle", "start": "start",
                          "end": "end"}[it["anchor"]]
                weight = ' font-weight="600"' if it["weight"] == "bold" else ""
                style = ' font-style="italic"' if it["weight"] == "italic" else ""
                out.append(
                    '<text x="{x}" y="{y}" font-size="{fs}" fill="{f}" '
                    'text-anchor="{a}" dominant-baseline="central"{w}{st}>{c}</text>'
                    .format(x=it["x"], y=it["y"], fs=it["size"], f=it["fill"],
                            a=anchor, w=weight, st=style,
                            c=html.escape(it["content"])))

        out.append("</svg>")
        return "\n".join(out)

    # -- PNG renderer -----------------------------------------------------
    def to_image(self, scale=2):
        image = Image.new("RGB", (int(self.width * scale), int(self.height * scale)),
                          self.background)
        draw = ImageDraw.Draw(image)

        def S(v):
            return v * scale

        def dashed(points, colour, width, pattern=(7, 5)):
            on, off = pattern[0] * scale, pattern[1] * scale
            for (x1, y1), (x2, y2) in zip(points, points[1:]):
                dx, dy = x2 - x1, y2 - y1
                length = (dx * dx + dy * dy) ** 0.5
                if length == 0:
                    continue
                ux, uy = dx / length, dy / length
                position = 0.0
                while position < length:
                    end = min(position + on, length)
                    draw.line([(x1 + ux * position, y1 + uy * position),
                               (x1 + ux * end, y1 + uy * end)],
                              fill=colour, width=width)
                    position = end + off

        def arrowhead(tip, tail, kind, colour):
            import math
            angle = math.atan2(tip[1] - tail[1], tip[0] - tail[0])
            size = 13 * scale
            spread = math.radians(22)
            left = (tip[0] - size * math.cos(angle - spread),
                    tip[1] - size * math.sin(angle - spread))
            right = (tip[0] - size * math.cos(angle + spread),
                     tip[1] - size * math.sin(angle + spread))
            if kind == "filled":
                draw.polygon([tip, left, right], fill=colour)
            else:
                w = max(1, int(1.8 * scale))
                draw.line([left, tip], fill=colour, width=w)
                draw.line([right, tip], fill=colour, width=w)

        for kind, it in self.items:
            if kind == "rect":
                xy = [S(it["x"]), S(it["y"]),
                      S(it["x"] + it["w"]), S(it["y"] + it["h"])]
                width = max(1, int(it["width"] * scale))
                if it["dash"]:
                    x0, y0, x1, y1 = xy
                    dashed([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
                           it["stroke"], width)
                elif it["radius"]:
                    draw.rounded_rectangle(xy, radius=S(it["radius"]),
                                           fill=it["fill"], outline=it["stroke"],
                                           width=width)
                else:
                    draw.rectangle(xy, fill=it["fill"], outline=it["stroke"],
                                   width=width)
            elif kind == "ellipse":
                draw.ellipse([S(it["cx"] - it["rx"]), S(it["cy"] - it["ry"]),
                              S(it["cx"] + it["rx"]), S(it["cy"] + it["ry"])],
                             fill=it["fill"], outline=it["stroke"],
                             width=max(1, int(it["width"] * scale)))
            elif kind == "poly":
                draw.polygon([(S(x), S(y)) for x, y in it["points"]],
                             fill=it["fill"], outline=it["stroke"])
            elif kind == "line":
                points = [(S(x), S(y)) for x, y in it["points"]]
                width = max(1, int(it["width"] * scale))
                if it["dash"]:
                    dashed(points, it["stroke"], width)
                else:
                    draw.line(points, fill=it["stroke"], width=width,
                              joint="curve")
                if it["arrow"]:
                    arrowhead(points[-1], points[-2], it["arrow"], it["stroke"])
                if it["start_arrow"]:
                    arrowhead(points[0], points[1], it["start_arrow"], it["stroke"])
            elif kind == "text":
                anchor = {"middle": "mm", "start": "lm", "end": "rm"}[it["anchor"]]
                draw.text((S(it["x"]), S(it["y"])), it["content"],
                          font=font(int(it["size"] * scale), it["weight"]),
                          fill=it["fill"], anchor=anchor)

        return image

    # -- output -----------------------------------------------------------
    def save(self, path_without_extension, scale=2):
        base = Path(path_without_extension)
        base.parent.mkdir(parents=True, exist_ok=True)
        svg_path = base.with_suffix(".svg")
        png_path = base.with_suffix(".png")
        svg_path.write_text(self.to_svg(), encoding="utf-8")
        self.to_image(scale=scale).save(png_path, "PNG")
        return svg_path, png_path
