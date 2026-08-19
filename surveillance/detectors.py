"""YOLO inference wrapper.

Ultralytics is imported lazily inside :meth:`DetectorBundle.load` so that the
rest of the package - analytics, alerting, storage - can be imported and tested
on a machine with no PyTorch installed.
"""

import logging
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Detection:
    """One box produced by one detector."""

    detector: str          # which DetectorConfig produced it, e.g. "weapon"
    label: str             # the model's own class name, e.g. "Handgun"
    confidence: float
    box: tuple             # (x1, y1, x2, y2) as ints, in frame pixel space

    @property
    def centroid(self):
        x1, y1, x2, y2 = self.box
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def area(self):
        x1, y1, x2, y2 = self.box
        return max(0, x2 - x1) * max(0, y2 - y1)

    def iou(self, other):
        """Intersection over union with another detection's box."""
        ax1, ay1, ax2, ay2 = self.box
        bx1, by1, bx2, by2 = other.box
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if inter == 0:
            return 0.0
        union = self.area + other.area - inter
        return inter / union if union else 0.0


class DetectorBundle:
    """Holds every enabled model and runs them over a frame.

    The models are independent single-purpose networks rather than one
    multi-class network, which is what the three separate training runs
    produced. Running them in sequence is the honest cost of that choice and is
    measured by :func:`tools.evaluate.benchmark_latency`.
    """

    def __init__(self, detector_configs):
        self.configs = tuple(d for d in detector_configs if d.enabled)
        self._models = {}
        self._loaded = False
        # Confidence thresholds an operator has changed from the dashboard.
        # Kept separate from the frozen config so a restart returns to the
        # reviewed defaults in config.yaml rather than to whatever was last
        # tried at 3am.
        self._conf_overrides = {}

    def confidence(self, detector_id):
        cfg = next((c for c in self.configs if c.id == detector_id), None)
        if cfg is None:
            return None
        return self._conf_overrides.get(detector_id, cfg.conf)

    def set_confidence(self, detector_id, value):
        """Override one detector's threshold for this run. Returns the value set."""
        value = max(0.01, min(0.99, float(value)))
        self._conf_overrides[detector_id] = value
        log.info("confidence for %s set to %.2f", detector_id, value)
        return value

    def load(self):
        """Import ultralytics and instantiate every enabled model."""
        if self._loaded:
            return
        from ultralytics import YOLO  # noqa: PLC0415 - deliberately lazy

        for cfg in self.configs:
            log.info("loading detector %s from %s", cfg.id, cfg.weights)
            self._models[cfg.id] = YOLO(cfg.weights)
        self._loaded = True

    def class_names(self, detector_id):
        model = self._models.get(detector_id)
        return dict(model.names) if model else {}

    def threshold_for(self, cfg, label):
        """Confidence a detection of ``label`` must clear.

        A model's classes rarely perform alike. The fire checkpoint validates at
        AP@50 = 0.648 for `fire` but only 0.269 for `smoke`, so holding both to
        one number either floods the operator with smoke false positives or
        throws away usable fire detections. Per-class thresholds let each class
        sit at its own operating point.
        """
        base = self.confidence(cfg.id)
        if not cfg.class_conf:
            return base
        return float(cfg.class_conf_map.get(str(label).lower(), base))

    def _inference_floor(self, cfg):
        """Lowest threshold any class needs, so nothing is discarded too early."""
        base = self.confidence(cfg.id)
        if not cfg.class_conf:
            return base
        return min([base] + list(cfg.class_conf_map.values()))

    def detect(self, frame):
        """Run every enabled model over ``frame``.

        Returns ``(detections, elapsed_ms_by_detector)``.
        """
        if not self._loaded:
            self.load()

        detections = []
        timings = {}
        for cfg in self.configs:
            model = self._models[cfg.id]
            started = time.perf_counter()
            result = model(frame, conf=self._inference_floor(cfg), verbose=False)[0]
            timings[cfg.id] = (time.perf_counter() - started) * 1000.0

            for row in result.boxes.data.tolist():
                x1, y1, x2, y2, confidence, class_id = row
                class_id = int(class_id)
                if cfg.keep_classes and class_id not in cfg.keep_classes:
                    continue
                # Always read the label from the checkpoint. Hard-coding class
                # order silently breaks whenever a model is retrained with a
                # different data.yaml.
                label = model.names[class_id]
                if float(confidence) < self.threshold_for(cfg, label):
                    continue
                detections.append(
                    Detection(
                        detector=cfg.id,
                        label=label,
                        confidence=float(confidence),
                        box=(int(x1), int(y1), int(x2), int(y2)),
                    )
                )
        return detections, timings
