"""YOLO model loading and inference."""

import logging
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Detection:
    detector: str
    label: str
    confidence: float
    box: tuple

    @property
    def centroid(self):
        x1, y1, x2, y2 = self.box
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def area(self):
        x1, y1, x2, y2 = self.box
        return max(0, x2 - x1) * max(0, y2 - y1)

    def iou(self, other):
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
    """The enabled models, run in sequence over each frame."""

    def __init__(self, detector_configs):
        self.configs = tuple(d for d in detector_configs if d.enabled)
        self._models = {}
        self._loaded = False
        # Dashboard tweaks live here, not in the frozen config, so a restart
        # goes back to the reviewed defaults.
        self._conf_overrides = {}

    def confidence(self, detector_id):
        cfg = next((c for c in self.configs if c.id == detector_id), None)
        if cfg is None:
            return None
        return self._conf_overrides.get(detector_id, cfg.conf)

    def set_confidence(self, detector_id, value):
        value = max(0.01, min(0.99, float(value)))
        self._conf_overrides[detector_id] = value
        log.info("confidence for %s set to %.2f", detector_id, value)
        return value

    def load(self):
        if self._loaded:
            return
        # Imported here so the rest of the package works without PyTorch.
        from ultralytics import YOLO

        for cfg in self.configs:
            log.info("loading detector %s from %s", cfg.id, cfg.weights)
            self._models[cfg.id] = YOLO(cfg.weights)
        self._loaded = True

    def class_names(self, detector_id):
        model = self._models.get(detector_id)
        return dict(model.names) if model else {}

    def threshold_for(self, cfg, label):
        """Classes in one model can need very different thresholds - fire
        validates at AP 0.648, smoke at 0.269."""
        base = self.confidence(cfg.id)
        if not cfg.class_conf:
            return base
        return float(cfg.class_conf_map.get(str(label).lower(), base))

    def _inference_floor(self, cfg):
        base = self.confidence(cfg.id)
        if not cfg.class_conf:
            return base
        return min([base] + list(cfg.class_conf_map.values()))

    def detect(self, frame):
        """Returns (detections, elapsed_ms_by_detector)."""
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
                # Read the name from the checkpoint; hard-coding class order
                # breaks silently on retrain.
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
