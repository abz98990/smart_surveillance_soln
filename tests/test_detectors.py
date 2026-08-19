"""Per-class confidence thresholds, exercised without loading a model."""

import unittest

from surveillance.config import DetectorConfig, load_config
from surveillance.detectors import DetectorBundle, Detection


class ThresholdTests(unittest.TestCase):
    def setUp(self):
        self.cfg = DetectorConfig(
            id="fire", weights="weights_fire/best.pt", conf=0.50,
            class_conf=(("fire", 0.50), ("smoke", 0.70)),
        )
        self.bundle = DetectorBundle([self.cfg])

    def test_class_specific_threshold_is_used(self):
        self.assertAlmostEqual(self.bundle.threshold_for(self.cfg, "fire"), 0.50)
        self.assertAlmostEqual(self.bundle.threshold_for(self.cfg, "smoke"), 0.70)

    def test_label_matching_is_case_insensitive(self):
        self.assertAlmostEqual(self.bundle.threshold_for(self.cfg, "SMOKE"), 0.70)

    def test_unlisted_class_falls_back_to_the_base_threshold(self):
        self.assertAlmostEqual(self.bundle.threshold_for(self.cfg, "steam"), 0.50)

    def test_inference_floor_is_the_lowest_threshold_needed(self):
        # Must run low enough that no class is dropped before its own
        # threshold is applied.
        self.assertAlmostEqual(self.bundle._inference_floor(self.cfg), 0.50)

        low = DetectorConfig(id="x", weights="w.pt", conf=0.60,
                             class_conf=(("fire", 0.35),))
        self.assertAlmostEqual(DetectorBundle([low])._inference_floor(low), 0.35)

    def test_a_detector_without_overrides_is_unaffected(self):
        plain = DetectorConfig(id="weapon", weights="weights_gun/best.pt", conf=0.4)
        bundle = DetectorBundle([plain])
        self.assertAlmostEqual(bundle.threshold_for(plain, "Handgun"), 0.4)
        self.assertAlmostEqual(bundle._inference_floor(plain), 0.4)

    def test_a_dashboard_override_still_applies_to_unlisted_classes(self):
        self.bundle.set_confidence("fire", 0.65)
        self.assertAlmostEqual(self.bundle.threshold_for(self.cfg, "steam"), 0.65)


class ShippedConfigTests(unittest.TestCase):
    def test_smoke_is_held_stricter_than_fire(self):
        fire = load_config(load_env=False).detector("fire")
        thresholds = fire.class_conf_map
        self.assertIn("smoke", thresholds)
        self.assertGreater(thresholds["smoke"], thresholds.get("fire", fire.conf),
                           "smoke validates far worse than fire")


class DetectionGeometryTests(unittest.TestCase):
    def test_iou_and_area(self):
        a = Detection("d", "x", 0.9, (0, 0, 10, 10))
        b = Detection("d", "x", 0.9, (5, 0, 15, 10))
        self.assertEqual(a.area, 100)
        self.assertAlmostEqual(a.iou(b), 50 / 150)

    def test_disjoint_boxes_have_zero_iou(self):
        a = Detection("d", "x", 0.9, (0, 0, 10, 10))
        b = Detection("d", "x", 0.9, (50, 50, 60, 60))
        self.assertEqual(a.iou(b), 0.0)

    def test_centroid(self):
        self.assertEqual(Detection("d", "x", 0.9, (0, 0, 10, 20)).centroid, (5.0, 10.0))


if __name__ == "__main__":
    unittest.main()
