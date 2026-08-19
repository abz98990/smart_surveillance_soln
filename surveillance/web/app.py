"""Flask dashboard: live streams, the alert log, and runtime configuration."""

import logging
import time

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

log = logging.getLogger(__name__)

BOUNDARY = "frame"
PLACEHOLDER_WAIT = 0.5


def _mjpeg(buffer):
    """Yield an endless multipart stream from a camera's frame buffer."""
    while True:
        jpeg = buffer.wait_for_frame(timeout=2.0)
        if jpeg is None:
            time.sleep(PLACEHOLDER_WAIT)
            continue
        yield (
            b"--" + BOUNDARY.encode() + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
            + jpeg + b"\r\n"
        )


def create_app(service, store, config):
    app = Flask(__name__)
    app.config["SERVICE"] = service
    app.config["STORE"] = store
    app.config["APP_CONFIG"] = config

    @app.template_filter("clock")
    def clock(value):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value))

    @app.template_filter("ago")
    def ago(value):
        seconds = max(0, time.time() - value)
        for limit, unit, name in ((60, 1, "s"), (3600, 60, "m"), (86400, 3600, "h")):
            if seconds < limit:
                return "{:.0f}{} ago".format(seconds / unit, name)
        return "{:.0f}d ago".format(seconds / 86400)

    # -- pages -------------------------------------------------------------
    @app.route("/")
    def dashboard():
        return render_template(
            "dashboard.html",
            status=service.status,
            alerts=store.recent(limit=12),
            severity_counts=store.counts_by_severity(),
            event_counts=store.counts_by_event(),
        )

    @app.route("/events")
    def events():
        camera_id = request.args.get("camera") or None
        severity = request.args.get("severity") or None
        limit = min(500, max(10, request.args.get("limit", 100, type=int)))
        return render_template(
            "events.html",
            alerts=store.recent(limit=limit, camera_id=camera_id, severity=severity),
            cameras=config.enabled_cameras,
            selected_camera=camera_id,
            selected_severity=severity,
            limit=limit,
        )

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        if request.method == "POST":
            for detector in config.enabled_detectors:
                field = "conf_{}".format(detector.id)
                if field in request.form:
                    try:
                        service.detectors.set_confidence(
                            detector.id, float(request.form[field])
                        )
                    except (TypeError, ValueError):
                        log.warning("ignored bad confidence for %s", detector.id)

            for event, rule in list(service.alerts.rules.items()):
                cooldown = request.form.get("cooldown_{}".format(event), type=float)
                frames = request.form.get("frames_{}".format(event), type=int)
                if cooldown is None and frames is None:
                    continue
                from dataclasses import replace  # noqa: PLC0415

                service.alerts.rules[event] = replace(
                    rule,
                    cooldown_seconds=max(0.0, cooldown) if cooldown is not None
                    else rule.cooldown_seconds,
                    min_consecutive_frames=max(1, frames) if frames is not None
                    else rule.min_consecutive_frames,
                )
            return redirect(url_for("settings", saved=1))

        return render_template(
            "settings.html",
            detectors=[
                {
                    "id": d.id,
                    "weights": d.weights,
                    "configured": d.conf,
                    "active": service.detectors.confidence(d.id),
                }
                for d in config.enabled_detectors
            ],
            rules=service.alerts.rules,
            email_enabled="email" in service.alerts.channels,
            storage=config.storage,
            saved=request.args.get("saved"),
        )

    # -- media -------------------------------------------------------------
    @app.route("/stream/<camera_id>")
    def stream(camera_id):
        buffer = service.buffer(camera_id)
        if buffer is None:
            abort(404)
        return Response(
            _mjpeg(buffer),
            mimetype="multipart/x-mixed-replace; boundary=" + BOUNDARY,
        )

    @app.route("/snapshot/<path:filename>")
    def snapshot(filename):
        # send_from_directory rejects traversal outside the snapshot folder.
        return send_from_directory(store.snapshot_dir, filename)

    # -- actions and API ---------------------------------------------------
    @app.route("/alerts/<int:alert_id>/ack", methods=["POST"])
    def acknowledge(alert_id):
        store.acknowledge(alert_id)
        if request.headers.get("Accept", "").startswith("application/json"):
            return jsonify({"ok": True, "id": alert_id})
        return redirect(request.referrer or url_for("dashboard"))

    @app.route("/api/status")
    def api_status():
        return jsonify(service.status)

    @app.route("/api/alerts")
    def api_alerts():
        limit = min(500, max(1, request.args.get("limit", 50, type=int)))
        return jsonify(
            [
                {
                    "id": a.id,
                    "at": a.at,
                    "timestamp": a.timestamp,
                    "camera": a.camera_id,
                    "event": a.event_type,
                    "severity": a.severity,
                    "detail": a.detail,
                    "confidence": a.confidence,
                    "acknowledged": a.acknowledged,
                    "snapshot": a.snapshot,
                }
                for a in store.recent(limit=limit)
            ]
        )

    return app
