"""Capture, detection and analysis loop.

One :class:`CameraWorker` thread per camera. Each worker owns its own analytics
state but shares the loaded models, because Ultralytics inference is not
re-entrant - a lock serialises it. That is a real scaling limit and is measured
rather than hidden: see ``tools/evaluate.py --benchmark``.
"""

import logging
import threading
import time

from surveillance.analytics import AnalyticsEngine
from surveillance.detectors import DetectorBundle
from surveillance.render import annotate, encode_jpeg, stamp_status

log = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5.0
ALERT_BANNER_SECONDS = 5.0


class FrameBuffer:
    """Holds the most recent annotated frame for one camera."""

    def __init__(self):
        self._lock = threading.Lock()
        self._jpeg = None
        self._updated_at = 0.0
        self._new_frame = threading.Condition(self._lock)

    def publish(self, jpeg_bytes):
        if not jpeg_bytes:
            return
        with self._new_frame:
            self._jpeg = jpeg_bytes
            self._updated_at = time.time()
            self._new_frame.notify_all()

    def latest(self):
        with self._lock:
            return self._jpeg

    def wait_for_frame(self, timeout=2.0):
        """Block until a newer frame arrives, then return it."""
        with self._new_frame:
            self._new_frame.wait(timeout=timeout)
            return self._jpeg

    @property
    def age(self):
        with self._lock:
            return time.time() - self._updated_at if self._updated_at else float("inf")

    @property
    def is_live(self):
        return self.age < 5.0


class CameraWorker(threading.Thread):
    def __init__(self, camera, config, detectors, alert_manager, inference_lock):
        super().__init__(name="camera-{}".format(camera.id), daemon=True)
        self.camera = camera
        self.config = config
        self.detectors = detectors
        self.alerts = alert_manager
        self.inference_lock = inference_lock
        self.buffer = FrameBuffer()
        self.analytics = AnalyticsEngine(camera.id, config.analytics)

        self._stop = threading.Event()
        self._colours = {d.id: d.colour for d in config.enabled_detectors}
        self._interval = 1.0 / camera.process_fps if camera.process_fps > 0 else 0.0
        self._last_alert = None
        self._last_alert_at = 0.0

        self.frames_processed = 0
        self.measured_fps = 0.0
        self.last_error = ""

    def stop(self):
        self._stop.set()

    def _open(self):
        import cv2  # noqa: PLC0415 - keeps the module importable without OpenCV

        capture = cv2.VideoCapture(self.camera.source)
        if not capture.isOpened():
            capture.release()
            return None
        return capture

    def run(self):
        while not self._stop.is_set():
            capture = self._open()
            if capture is None:
                self.last_error = "cannot open source {!r}".format(self.camera.source)
                log.error("[%s] %s", self.camera.id, self.last_error)
                if self._stop.wait(RECONNECT_DELAY_SECONDS):
                    break
                continue

            self.last_error = ""
            log.info("[%s] capture opened on %r", self.camera.id, self.camera.source)
            try:
                self._loop(capture)
            finally:
                capture.release()

            if not self._stop.is_set():
                log.warning("[%s] stream ended, reconnecting", self.camera.id)
                if self._stop.wait(RECONNECT_DELAY_SECONDS):
                    break

    def _loop(self, capture):
        next_process_at = 0.0
        window_started, window_frames = time.perf_counter(), 0

        while not self._stop.is_set():
            ok, frame = capture.read()
            if not ok or frame is None:
                return  # let run() reconnect

            now = time.time()
            if now < next_process_at:
                # Surplus frames are dropped rather than queued, so the newest
                # frame is always the one that gets analysed.
                continue
            next_process_at = now + self._interval

            self._process(frame, now)

            window_frames += 1
            elapsed = time.perf_counter() - window_started
            if elapsed >= 1.0:
                self.measured_fps = window_frames / elapsed
                window_started, window_frames = time.perf_counter(), 0

    def _process(self, frame, now):
        with self.inference_lock:
            detections, _ = self.detectors.detect(frame)

        events = self.analytics.update(detections, now)
        annotated = annotate(frame, detections, self._colours)

        fired = self.alerts.submit(
            events,
            camera_id=self.camera.id,
            now=now,
            snapshot=lambda: encode_jpeg(annotated, quality=85),
        )
        if fired:
            self._last_alert = fired[0]
            self._last_alert_at = now

        banner = None
        if self._last_alert and (now - self._last_alert_at) < ALERT_BANNER_SECONDS:
            banner = self._last_alert

        stamp_status(annotated, self.camera.name, self.measured_fps, banner)
        self.buffer.publish(encode_jpeg(annotated, self.config.web.stream_quality))
        self.frames_processed += 1

    @property
    def status(self):
        return {
            "id": self.camera.id,
            "name": self.camera.name,
            "source": str(self.camera.source),
            "network": self.camera.is_network_source,
            "live": self.buffer.is_live,
            "fps": round(self.measured_fps, 1),
            "frames": self.frames_processed,
            "tracks": len(self.analytics.tracks),
            "error": self.last_error,
        }


class SurveillanceService:
    """Owns every worker, the shared models and the background retention job."""

    def __init__(self, config, store, alert_manager):
        self.config = config
        self.store = store
        self.alerts = alert_manager
        self.detectors = DetectorBundle(config.enabled_detectors)
        self.workers = {}
        self._inference_lock = threading.Lock()
        self._stop = threading.Event()
        self._housekeeper = None
        self.started_at = 0.0

    def start(self, preload=True):
        if preload:
            self.detectors.load()
        self.alerts.start()

        for camera in self.config.enabled_cameras:
            worker = CameraWorker(
                camera, self.config, self.detectors, self.alerts, self._inference_lock
            )
            self.workers[camera.id] = worker
            worker.start()

        self._housekeeper = threading.Thread(
            target=self._housekeeping_loop, name="housekeeping", daemon=True
        )
        self._housekeeper.start()
        self.started_at = time.time()
        log.info("service started with %d camera(s)", len(self.workers))

    def stop(self):
        self._stop.set()
        for worker in self.workers.values():
            worker.stop()
        for worker in self.workers.values():
            worker.join(timeout=5)
        self.alerts.stop()
        log.info("service stopped")

    def _housekeeping_loop(self):
        """Enforce the snapshot retention window once an hour."""
        while not self._stop.wait(3600):
            try:
                removed = self.store.purge_expired()
                if removed:
                    log.info("retention purge removed %d expired alert(s)", removed)
            except Exception:
                log.exception("retention purge failed")

    def buffer(self, camera_id):
        worker = self.workers.get(camera_id)
        return worker.buffer if worker else None

    @property
    def status(self):
        return {
            "uptime_seconds": time.time() - self.started_at if self.started_at else 0,
            "cameras": [w.status for w in self.workers.values()],
            "unacknowledged": self.store.unacknowledged_count(),
        }
