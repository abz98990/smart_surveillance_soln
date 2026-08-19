#!/usr/bin/env python3
"""Smart Surveillance System - single entry point.

    python run.py                 # detection + dashboard on http://127.0.0.1:8000
    python run.py --display       # also open a local OpenCV window
    python run.py --headless      # detection and alerting only, no web server
    python run.py --check         # verify configuration and weights, then exit
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from surveillance.alerts import AlertManager
from surveillance.channels import build_channels
from surveillance.config import PROJECT_ROOT, load_config
from surveillance.storage import EventStore

# surveillance.pipeline pulls in OpenCV, so it is imported inside main(). That
# keeps `--check` usable on a fresh clone before the heavy dependencies are
# installed, which is exactly when someone most wants to run it.

log = logging.getLogger("surveillance")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Smart Surveillance System")
    parser.add_argument("--config", default=None, help="path to config.yaml")
    parser.add_argument("--headless", action="store_true",
                        help="run detection and alerting without the dashboard")
    parser.add_argument("--display", action="store_true",
                        help="open a local OpenCV window showing every camera")
    parser.add_argument("--check", action="store_true",
                        help="validate configuration and model files, then exit")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args(argv)


def check_config(config):
    """Report anything that would stop a clean start. Returns a problem count."""
    problems = 0

    if not config.enabled_cameras:
        print("  [!] no cameras enabled in config.yaml")
        problems += 1
    for camera in config.enabled_cameras:
        kind = "network" if camera.is_network_source else "local device"
        print("  [ok] camera {:<8} {:<28} {}".format(camera.id, str(camera.source), kind))

    if not config.enabled_detectors:
        print("  [!] no detectors enabled in config.yaml")
        problems += 1
    for detector in config.enabled_detectors:
        path = PROJECT_ROOT / detector.weights
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print("  [ok] detector {:<8} {:<28} {:.1f} MB, conf {:.2f}".format(
                detector.id, detector.weights, size_mb, detector.conf))
            for label, threshold in sorted(detector.class_conf_map.items()):
                print("       {:<8}   class {:<10} conf {:.2f}".format(
                    "", label, threshold))
        else:
            print("  [!] detector {:<8} weights missing: {}".format(
                detector.id, detector.weights))
            problems += 1

    known_events = {
        "weapon_detected", "armed_person", "fire_detected",
        "smoke_detected", "loitering",
    }
    for rule in config.rules:
        marker = "ok" if rule.event in known_events else "! "
        if rule.event not in known_events:
            problems += 1
        print("  [{}] rule     {:<16} {:<9} {} frame(s), {:.0f}s cooldown -> {}".format(
            marker, rule.event, rule.severity, rule.min_consecutive_frames,
            rule.cooldown_seconds, ", ".join(rule.channels)))

    if config.email.is_configured:
        print("  [ok] email    configured for {} recipient(s)".format(
            len(config.email.recipients)))
    else:
        print("  [--] email    not configured (set SSS_SMTP_* in .env to enable)")

    for module, package, required in (("cv2", "opencv-python", True),
                                      ("ultralytics", "ultralytics", True),
                                      ("flask", "Flask", True),
                                      ("plyer", "plyer", False)):
        try:
            __import__(module)
            print("  [ok] python   {} installed".format(package))
        except ImportError:
            if required:
                print("  [!] python   {} is missing: pip install -r requirements.txt"
                      .format(package))
                problems += 1
            else:
                print("  [--] python   {} missing; desktop alerts will be skipped"
                      .format(package))

    return problems


def run_display_loop(service, stop_signal):
    """Optional local window: every camera tiled into one canvas."""
    import cv2
    import numpy as np

    from surveillance.render import compose_grid

    window = "Smart Surveillance System"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 1280, 720)

    while not stop_signal():
        frames = []
        for worker in service.workers.values():
            jpeg = worker.buffer.latest()
            if jpeg:
                frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    frames.append(frame)

        if frames:
            cv2.imshow(window, compose_grid(frames, 1280, 720))
        if cv2.waitKey(30) & 0xFF in (ord("q"), 27):
            break

    cv2.destroyAllWindows()


def main(argv=None):
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    config = load_config(args.config)

    if args.check:
        print("Smart Surveillance System - configuration check\n")
        problems = check_config(config)
        print("\n{} problem(s) found.".format(problems) if problems
              else "\nConfiguration is complete.")
        return 1 if problems else 0

    from surveillance.pipeline import SurveillanceService

    store = EventStore(config.storage, root=PROJECT_ROOT)
    alert_manager = AlertManager(
        rules=config.rules,
        store=store,
        channels=build_channels(config),
        camera_names={c.id: c.name for c in config.cameras},
    )
    service = SurveillanceService(config, store, alert_manager)

    stopping = {"flag": False}

    def request_stop(*_):
        stopping["flag"] = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    log.info("loading models, this takes a moment on first run")
    service.start()

    try:
        if args.headless and not args.display:
            while not stopping["flag"]:
                time.sleep(0.5)
        elif args.headless and args.display:
            run_display_loop(service, lambda: stopping["flag"])
        else:
            from surveillance.web import create_app

            app = create_app(service, store, config)
            if args.display:
                import threading

                threading.Thread(
                    target=run_display_loop,
                    args=(service, lambda: stopping["flag"]),
                    daemon=True,
                ).start()

            log.info("dashboard on http://%s:%d", config.web.host, config.web.port)
            # threaded=True so one open MJPEG stream cannot block the other routes.
            app.run(host=config.web.host, port=config.web.port,
                    threaded=True, debug=False, use_reloader=False)
    finally:
        service.stop()

    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
