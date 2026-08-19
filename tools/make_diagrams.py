#!/usr/bin/env python3
"""Regenerates the six UML figures into docs/diagrams/ as SVG and PNG.

    python tools/make_diagrams.py

Run this after any architectural change, so the figures cannot drift away from
the code the way the earlier hand-drawn ones did.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagram_kit import (  # noqa: E402
    BLUE, BLUE_DARK, GREEN, GREY, INK, LINE, MUTED, RED, SAND, WHITE, Canvas,
)

OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"

INCLUDE = "«include»"
EXTEND = "«extend»"


# ---------------------------------------------------------------- A.1
def use_case_diagram():
    c = Canvas(1620, 1080)
    c.title("Smart Surveillance System – Use Cases")

    # System boundary
    c.rect(330, 70, 960, 950, fill="#F7FAFD", stroke=MUTED, width=2)
    c.text(810, 96, "Smart Surveillance System", size=16, weight="bold", fill=MUTED)

    # Actors
    c.system_actor(150, 300, "Camera")
    c.text(150, 350, "USB or IP", size=12, fill=MUTED)
    c.actor(1470, 430, "Administrator")

    # Detection package
    c.rect(390, 300, 500, 200, fill=WHITE, stroke=MUTED, width=2, dash=True)
    c.text(640, 322, "Detection", size=14, fill=MUTED)

    c.use_case(560, 170, ["Capture", "Video Feed"], rx=105, ry=52)
    c.use_case(505, 410, ["Detect", "Person"], rx=88, ry=46)
    c.use_case(700, 410, ["Detect Weapon,", "Fire or Smoke"], rx=100, ry=46)
    c.use_case(600, 610, ["Analyse", "Behaviour"], rx=95, ry=48, fill=GREEN)
    c.use_case(600, 810, ["Raise Alert"], rx=95, ry=46, fill=SAND)
    c.use_case(960, 930, ["Notify by Email"], rx=100, ry=44, fill=GREY)

    c.use_case(1130, 190, ["View Live Feed"], rx=100, ry=44)
    c.use_case(1130, 350, ["Review", "Alert Log"], rx=100, ry=46)
    c.use_case(1130, 530, ["Acknowledge", "Alert"], rx=100, ry=46, fill=GREY)
    c.use_case(1130, 700, ["Configure", "Thresholds"], rx=100, ry=46)

    # Actor associations
    c.line([(225, 300), (455, 185)])
    for target in ((1230, 190), (1230, 350), (1230, 700)):
        c.line([(1425, 430), target[0] + 20, ] if False else
               [(1425, 430), (target[0], target[1])])

    # include chain: the base use case always performs the included one
    c.line([(560, 222), (540, 364)], dash=True, arrow="filled")
    c.text(470, 292, INCLUDE, size=13, fill=MUTED)
    c.line([(620, 222), (690, 364)], dash=True, arrow="filled")
    c.text(740, 292, INCLUDE, size=13, fill=MUTED)

    c.line([(520, 456), (575, 562)], dash=True, arrow="filled")
    c.line([(690, 456), (630, 562)], dash=True, arrow="filled")
    c.text(600, 528, INCLUDE, size=13, fill=MUTED)

    c.line([(600, 658), (600, 764)], dash=True, arrow="filled")
    c.text(668, 712, INCLUDE, size=13, fill=MUTED)

    # extend: optional behaviour points AT the base use case
    c.line([(910, 908), (686, 838)], dash=True, arrow="filled")
    c.text(820, 852, EXTEND, size=13, fill=MUTED)
    c.text(880, 985, "only when SMTP is configured", size=12, fill=MUTED)

    c.line([(1130, 484), (1130, 396)], dash=True, arrow="filled")
    c.text(1210, 442, EXTEND, size=13, fill=MUTED)

    # Note explaining the corrected relationship semantics
    c.rect(60, 760, 250, 210, fill="#FFFDF5", stroke=MUTED, width=2)
    c.lines_of_text(185, 862, [
        "Arrow direction:", "",
        "«include» points from the",
        "base to the behaviour it",
        "always performs.",
        "",
        "«extend» points from the",
        "optional behaviour to the",
        "base it may augment.",
    ], size=12, leading=19)

    return c, "A1_use_case"


# ---------------------------------------------------------------- A.2
def component_diagram():
    c = Canvas(1880, 900)
    c.title("Smart Surveillance System – Components")

    c.rect(60, 70, 1560, 780, fill="#F7FAFD", stroke=MUTED, width=2)
    c.text(840, 96, "Local server process", size=15, weight="bold", fill=MUTED)

    def caption(cx, y, text):
        c.text(cx, y, text, size=11, fill=MUTED)

    # -- external participants
    c.system_actor(150, 305, "Camera", w=150, h=54)
    caption(150, 350, "USB or RTSP")
    c.system_actor(1740, 660, "SMTP relay", w=150, h=54)
    caption(1740, 705, "external")

    # -- detection row
    caption(420, 222, "surveillance.pipeline")
    c.component(320, 240, 200, 130, ["Camera", "Worker"], fill=BLUE)

    c.rect(620, 150, 290, 400, fill=WHITE, stroke=MUTED, width=2, dash=True)
    c.text(765, 176, "DetectorBundle", size=14, weight="bold", fill=MUTED)
    c.component(660, 200, 210, 76, ["Person"], fill=GREEN, stereotype=False)
    c.component(660, 296, 210, 76, ["Weapon"], fill=RED, stereotype=False)
    c.component(660, 392, 210, 76, ["Fire / Smoke"], fill=BLUE, stereotype=False)

    caption(1100, 222, "tracking, loitering, weapon association")
    c.component(1000, 240, 200, 130, ["Analytics", "Engine"], fill=GREEN)

    caption(1410, 222, "debounce + cooldown")
    c.component(1310, 240, 200, 130, ["Alert", "Manager"], fill=SAND)

    # -- persistence and delivery row
    c.text(470, 762, "Flask + MJPEG", size=11, fill=MUTED, anchor="start")
    c.component(320, 600, 200, 130, ["Web", "Dashboard"], fill=BLUE)

    caption(800, 752, "SQLite + snapshots")
    c.component(700, 600, 200, 120, ["Event Store"], fill=GREY)

    caption(1410, 752, "desktop, email")
    c.component(1310, 600, 200, 120, ["Channels"], fill=GREY)

    # -- wiring
    c.line([(225, 305), (310, 305)], arrow="open")
    caption(267, 285, "frames")

    c.text(585, 272, "IDetect", size=12, fill=MUTED)
    c.lollipop(585, 305)
    c.line([(520, 305), (573, 305)])
    c.line([(597, 305), (614, 305)])
    for y in (238, 334, 430):
        c.line([(614, 305), (652, y)])

    c.line([(910, 305), (995, 305)], arrow="open")
    caption(952, 285, "detections")

    c.line([(1200, 305), (1305, 305)], arrow="open")
    caption(1252, 285, "events")

    c.line([(1410, 370), (1410, 595)], arrow="open")
    caption(1468, 480, "dispatch")

    # routed below the detector package rather than through it
    c.line([(1330, 370), (1330, 572), (800, 572), (800, 595)], arrow="open")
    caption(1065, 552, "alerts + snapshot")

    c.line([(1510, 660), (1660, 660)], arrow="open")
    caption(1585, 630, "SMTP over TLS")

    c.line([(700, 660), (528, 660)], arrow="open")
    caption(614, 638, "alert log")

    c.line([(420, 370), (420, 595)], arrow="open")
    c.text(406, 470, "annotated", size=11, fill=MUTED, anchor="end")
    c.text(406, 488, "frames", size=11, fill=MUTED, anchor="end")

    c.line([(420, 730), (420, 792)])
    c.lollipop(420, 803, "HTTP :8000", side="right")

    return c, "A2_component"


# ---------------------------------------------------------------- A.3
def package_diagram():
    c = Canvas(1520, 1000)
    c.title("Package Structure and Dependencies")

    c.folder(600, 90, 320, 96, "run.py", ["entry point"], fill=SAND)

    c.folder(80, 260, 300, 130, "surveillance.config",
             ["config.yaml + environment", "no secrets on disk"], fill=GREY)
    c.folder(600, 260, 320, 130, "surveillance.pipeline",
             ["CameraWorker per camera", "SurveillanceService"], fill=BLUE)
    c.folder(1130, 260, 310, 130, "surveillance.web",
             ["Flask dashboard", "MJPEG streaming"], fill=BLUE)

    c.folder(80, 500, 300, 130, "surveillance.detectors",
             ["YOLO11 inference", "lazy ultralytics import"], fill=GREEN)
    c.folder(440, 500, 300, 130, "surveillance.analytics",
             ["tracking, loitering,", "weapon association"], fill=GREEN)
    c.folder(800, 500, 300, 130, "surveillance.alerts",
             ["debounce, cooldown,", "threaded dispatch"], fill=SAND)
    c.folder(1160, 500, 280, 130, "surveillance.storage",
             ["SQLite event log", "snapshot retention"], fill=GREY)

    c.folder(300, 760, 300, 120, "surveillance.render",
             ["annotation, letterboxing"], fill=GREY)
    c.folder(660, 760, 280, 120, "surveillance.geometry",
             ["pure sizing helpers"], fill=GREY)
    c.folder(1000, 760, 300, 120, "surveillance.channels",
             ["desktop, email"], fill=GREY)

    def dep(x1, y1, x2, y2, label=None, lx=None, ly=None):
        c.line([(x1, y1), (x2, y2)], dash=True, arrow="filled")
        if label:
            c.text(lx or (x1 + x2) / 2, ly or (y1 + y2) / 2, label,
                   size=12, fill=MUTED)

    dep(700, 186, 700, 254)
    dep(790, 186, 1230, 254)
    dep(600, 152, 262, 254)

    dep(680, 390, 300, 496)
    dep(740, 390, 600, 496)
    dep(820, 390, 930, 496)
    # routed down the gap between detectors and analytics rather than over them
    c.line([(600, 330), (410, 330), (410, 752)], dash=True, arrow="filled")

    dep(950, 560, 1155, 560)
    dep(980, 630, 1120, 756)
    dep(1230, 390, 1000, 500)
    dep(1240, 390, 1300, 496)

    dep(450, 810, 730, 810)

    c.rect(80, 880, 380, 90, fill="#FFFDF5", stroke=MUTED, width=2)
    c.lines_of_text(270, 925, [
        "Dashed arrow = depends on (imports).",
        "No cycles: analytics and storage import nothing from the pipeline.",
    ], size=12, leading=22)

    return c, "A3_package"


# ---------------------------------------------------------------- A.4
def deployment_diagram():
    c = Canvas(1620, 1000)
    c.title("Deployment")

    # Devices
    c.node3d(80, 200, 250, 130, "USB Camera", fill=GREY)
    c.lines_of_text(205, 280, ["device index 0"], size=13)
    c.node3d(80, 430, 250, 130, "IP Camera", fill=GREY)
    c.lines_of_text(205, 510, ["RTSP stream"], size=13)

    # Local server
    c.node3d(470, 150, 720, 720, "Local Server  (Windows workstation, CPU inference)",
             fill="#EDF3F9", depth=22)
    c.node3d(520, 250, 620, 380, "Python 3.9+ runtime", fill=WHITE, depth=16)

    c.node3d(560, 330, 250, 110, "Surveillance Service", fill=BLUE, depth=12,
             label_size=13)
    c.lines_of_text(685, 400, ["CameraWorker, YOLO11"], size=12)

    c.node3d(850, 330, 250, 110, "Flask Dashboard", fill=BLUE, depth=12,
             label_size=13)
    c.lines_of_text(975, 400, ["binds 127.0.0.1:8000"], size=12)

    c.node3d(560, 480, 250, 110, "Alert Manager", fill=SAND, depth=12,
             label_size=13)
    c.lines_of_text(685, 550, ["debounce + dispatch"], size=12)

    c.rect(850, 480, 250, 110, fill=WHITE)
    c.text(975, 505, "«artifact»", size=11, fill=MUTED)
    c.text(975, 530, "surveillance.db", size=14, weight="bold")
    c.lines_of_text(975, 562, ["+ snapshots, 30 day", "retention"], size=12)

    c.node3d(520, 700, 620, 120, "Model weights", fill=GREY, depth=14,
             label_size=13)
    c.lines_of_text(830, 775, ["weights_people / weights_gun / weights_fire  (best.pt)"],
                    size=12)

    # External
    c.node3d(1290, 220, 250, 130, "Operator Browser", fill=GREY)
    c.lines_of_text(1415, 300, ["Chrome / Edge"], size=13)
    c.node3d(1290, 470, 250, 130, "SMTP Relay", fill=GREY)
    c.lines_of_text(1415, 550, ["external service"], size=13)

    # Communication paths
    c.line([(330, 265), (470, 350)])
    c.text(400, 288, "USB 2.0", size=12, fill=MUTED)

    c.line([(330, 495), (470, 430)])
    c.text(398, 428, "RTSP / TCP-IP", size=12, fill=MUTED)

    c.line([(1190, 400), (1290, 300)])
    c.text(1250, 366, "HTTP", size=12, fill=MUTED)

    c.line([(1190, 530), (1290, 530)])
    c.text(1240, 508, "SMTP / TLS", size=12, fill=MUTED)

    c.rect(80, 640, 320, 180, fill="#FFFDF5", stroke=MUTED, width=2)
    c.lines_of_text(240, 730, [
        "Video never leaves the local",
        "server. Only alert text and an",
        "optional snapshot are sent",
        "outbound, and only when SMTP",
        "is configured.",
    ], size=12, leading=22)

    return c, "A4_deployment"


# ---------------------------------------------------------------- B.1
def activity_diagram():
    c = Canvas(1220, 1840)
    c.title("Per-Frame Processing Activity")

    cx = 500

    def action(y, label, w=250, h=64, fill=BLUE, rows=None):
        c.rect(cx - w / 2, y, w, h, fill=fill, radius=12)
        c.lines_of_text(cx, y + h / 2, rows or [label], size=14)
        return y + h

    def arrow(y1, y2, x=None, label=None):
        x = cx if x is None else x
        c.line([(x, y1), (x, y2)], arrow="filled")
        if label:
            c.text(x + 14, (y1 + y2) / 2, label, size=12, fill=MUTED,
                   anchor="start")

    c.ellipse(cx, 100, 17, 17, fill=INK, stroke=INK)
    arrow(117, 148)

    y = action(148, "Capture Frame")
    arrow(y, y + 44)

    # Rate-limit decision
    dy = y + 44
    c.items.append(("poly", dict(points=[(cx, dy), (cx + 120, dy + 46),
                                         (cx, dy + 92), (cx - 120, dy + 46)],
                                 fill=SAND, stroke=LINE, width=2)))
    c.lines_of_text(cx, dy + 46, ["Due to process", "at target fps?"], size=13)
    c.text(cx - 200, dy + 30, "no – drop frame", size=12, fill=MUTED)
    c.line([(cx - 120, dy + 46), (cx - 320, dy + 46), (cx - 320, 180),
            (cx - 125, 180)], arrow="filled")
    c.text(cx + 20, dy + 108, "yes", size=12, fill=MUTED, anchor="start")

    y = dy + 92
    arrow(y, y + 44)
    y = action(y + 44, "Pre-process Frame")

    # Fork
    fork_y = y + 46
    c.rect(cx - 260, fork_y, 520, 12, fill=INK, stroke=INK)
    arrow(y, fork_y)

    branch_y = fork_y + 70
    for offset, label, fill in ((-215, "Detect Person", GREEN),
                                (0, "Detect Weapon", RED),
                                (215, "Detect Fire / Smoke", BLUE)):
        c.line([(cx + offset, fork_y + 12), (cx + offset, branch_y)], arrow="filled")
        c.rect(cx + offset - 100, branch_y, 200, 62, fill=fill, radius=12)
        c.lines_of_text(cx + offset, branch_y + 31, [label], size=13)

    join_y = branch_y + 62 + 50
    c.rect(cx - 260, join_y, 520, 12, fill=INK, stroke=INK)
    for offset in (-215, 0, 215):
        c.line([(cx + offset, branch_y + 62), (cx + offset, join_y)], arrow="filled")

    y = join_y + 12
    arrow(y, y + 44)
    y = action(y + 44, "", rows=["Update Person Tracks"], fill=GREEN, w=280)
    arrow(y, y + 44)
    y = action(y + 44, "", rows=["Evaluate Behaviour Rules"], fill=GREEN, w=280)

    # Event decision
    dy = y + 46
    c.items.append(("poly", dict(points=[(cx, dy), (cx + 130, dy + 46),
                                         (cx, dy + 92), (cx - 130, dy + 46)],
                                 fill=SAND, stroke=LINE, width=2)))
    c.lines_of_text(cx, dy + 46, ["Event raised?"], size=13)
    c.line([(cx, y), (cx, dy)], arrow="filled")

    # Right-hand alerting branch
    right = cx + 340
    c.line([(cx + 130, dy + 46), (right, dy + 46), (right, dy + 96)], arrow="filled")
    c.text(cx + 180, dy + 26, "yes", size=12, fill=MUTED)

    ay = dy + 96
    c.items.append(("poly", dict(points=[(right, ay), (right + 130, ay + 46),
                                         (right, ay + 92), (right - 130, ay + 46)],
                                 fill=SAND, stroke=LINE, width=2)))
    c.lines_of_text(right, ay + 46, ["Debounce and", "cooldown passed?"], size=12)

    by = ay + 92
    c.line([(right, by), (right, by + 44)], arrow="filled")
    c.text(right + 14, by + 22, "yes", size=12, fill=MUTED, anchor="start")
    c.rect(right - 125, by + 44, 250, 62, fill=SAND, radius=12)
    c.lines_of_text(right, by + 75, ["Record Alert", "+ Snapshot"], size=13)

    cy2 = by + 106
    c.line([(right, cy2), (right, cy2 + 44)], arrow="filled")
    c.rect(right - 125, cy2 + 44, 250, 62, fill=SAND, radius=12)
    c.lines_of_text(right, cy2 + 75, ["Dispatch Notifications", "(worker thread)"],
                    size=12)

    # suppressed path
    c.line([(right + 130, ay + 46), (right + 240, ay + 46),
            (right + 240, cy2 + 190)], arrow=None)
    c.text(right + 190, ay + 26, "no", size=12, fill=MUTED)

    # Merge back
    merge_y = cy2 + 190
    c.line([(right, cy2 + 106), (right, merge_y)], arrow=None)
    c.line([(cx - 130, dy + 46), (cx - 300, dy + 46), (cx - 300, merge_y)],
           arrow=None)
    c.text(cx - 210, dy + 26, "no", size=12, fill=MUTED)
    c.line([(cx - 300, merge_y), (right + 240, merge_y)], arrow=None)
    c.line([(cx, merge_y), (cx, merge_y + 50)], arrow="filled")

    y = action(merge_y + 50, "Annotate Frame")
    arrow(y, y + 44)
    y = action(y + 44, "", rows=["Publish to Dashboard"], w=280)

    arrow(y, y + 46)
    c.ellipse(cx, y + 68, 20, 20, fill=WHITE, stroke=INK, width=3)
    c.ellipse(cx, y + 68, 11, 11, fill=INK, stroke=INK)

    return c, "B1_activity"


# ---------------------------------------------------------------- B.2
def sequence_diagram():
    c = Canvas(2020, 1300)
    c.title("Alert Sequence for One Frame")

    lifelines = [
        ("Camera", 120, GREY),
        ("CameraWorker", 340, BLUE),
        ("DetectorBundle", 580, GREEN),
        ("AnalyticsEngine", 820, GREEN),
        ("AlertManager", 1070, SAND),
        ("EventStore", 1320, GREY),
        ("Channel", 1560, GREY),
        ("Administrator", 1810, GREY),
    ]
    top, bottom = 90, 1250
    for name, x, fill in lifelines:
        c.rect(x - 96, top, 192, 56, fill=fill)
        c.text(x, top + 28, name, size=14, weight="bold")
        c.line([(x, top + 56), (x, bottom)], dash=True, stroke=MUTED, width=2)

    X = {name: x for name, x, _ in lifelines}

    def activation(name, y1, y2, offset=0):
        c.rect(X[name] - 9 + offset, y1, 18, y2 - y1, fill="#DDE4EB", stroke=LINE)

    def message(src, dst, y, label, dashed=False, note=None):
        x1, x2 = X[src], X[dst]
        direction = 1 if x2 > x1 else -1
        c.line([(x1 + 9 * direction, y), (x2 - 9 * direction, y)],
               dash=dashed, arrow="open" if dashed else "filled")
        c.text((x1 + x2) / 2, y - 16, label, size=13)
        if note:
            c.text((x1 + x2) / 2, y + 17, note, size=11, fill=MUTED)

    activation("CameraWorker", 190, 1160)
    activation("DetectorBundle", 240, 330)
    activation("AnalyticsEngine", 380, 470)
    activation("AlertManager", 520, 1010)

    message("Camera", "CameraWorker", 190, "frame")
    message("CameraWorker", "DetectorBundle", 240, "detect(frame)")
    message("DetectorBundle", "CameraWorker", 320, "detections", dashed=True)
    message("CameraWorker", "AnalyticsEngine", 380, "update(detections, now)")
    message("AnalyticsEngine", "CameraWorker", 460, "events", dashed=True)
    message("CameraWorker", "AlertManager", 520, "submit(events)")

    # alt fragment: everything down to the divider is the "alert fires" branch
    fragment_x, fragment_w = 220, 1700
    c.fragment(fragment_x, 560, fragment_w, 460, "alt",
               "[ debounce and cooldown satisfied ]")
    activation("EventStore", 630, 710)
    activation("Channel", 800, 880)

    message("AlertManager", "EventStore", 630, "record(alert, snapshot)")
    message("EventStore", "AlertManager", 700, "alert id", dashed=True)
    message("AlertManager", "Channel", 770, "enqueue(alert)",
            note="returns immediately – dispatch runs on a worker thread")
    message("Channel", "Administrator", 850, "notify / email")

    # divider: below it is the "suppressed" branch
    c.line([(fragment_x, 900), (fragment_x + fragment_w, 900)],
           dash=True, stroke=MUTED, width=2)
    c.text(fragment_x + 20, 924,
           "[ suppressed – streak too short, or still cooling down ]",
           size=13, anchor="start")
    message("AlertManager", "CameraWorker", 975, "no alerts", dashed=True)

    # self-message back on the worker
    c.line([(X["CameraWorker"] + 9, 1070), (X["CameraWorker"] + 90, 1070),
            (X["CameraWorker"] + 90, 1108),
            (X["CameraWorker"] + 11, 1108)], arrow="filled")
    c.text(X["CameraWorker"] + 106, 1089, "publish(annotated frame)",
           size=13, anchor="start")

    c.line([(X["Administrator"], 1180), (X["CameraWorker"] + 12, 1180)],
           arrow="filled")
    c.text(1150, 1160, "GET /  (dashboard reads the frame buffer)", size=12,
           fill=MUTED)

    return c, "B2_sequence"


# ---------------------------------------------------------------- main
BUILDERS = [
    use_case_diagram,
    component_diagram,
    package_diagram,
    deployment_diagram,
    activity_diagram,
    sequence_diagram,
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for builder in BUILDERS:
        canvas, name = builder()
        svg_path, png_path = canvas.save(OUT / name)
        print("wrote {}  ({}x{})".format(png_path.name, canvas.width, canvas.height))
    print("\n{} figures in {}".format(len(BUILDERS), OUT))


if __name__ == "__main__":
    main()
