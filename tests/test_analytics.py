"""Weapon association, loitering, and hazard events."""

import unittest

from surveillance.analytics import AnalyticsEngine, containment
from surveillance.config import AnalyticsConfig
from surveillance.detectors import Detection


def person(box, confidence=0.9):
    return Detection(detector="person", label="person", confidence=confidence, box=box)


def handgun(box, confidence=0.8):
    return Detection(detector="weapon", label="Handgun", confidence=confidence, box=box)


class ContainmentTests(unittest.TestCase):
    def test_fully_inside_is_one(self):
        inner = handgun((110, 210, 130, 230))
        outer = person((100, 200, 200, 400))
        self.assertAlmostEqual(containment(inner, outer), 1.0)

    def test_disjoint_is_zero(self):
        self.assertEqual(containment(handgun((0, 0, 10, 10)),
                                     person((500, 500, 600, 700))), 0.0)

    def test_half_overlap(self):
        # Weapon box 20 wide; only 10 of it falls inside the person box.
        inner = handgun((90, 210, 110, 230))
        outer = person((100, 200, 200, 400))
        self.assertAlmostEqual(containment(inner, outer), 0.5)

    def test_iou_would_have_missed_this(self):
        # Why containment is used instead of IoU.
        inner = handgun((150, 300, 175, 320))
        outer = person((100, 200, 250, 600))
        self.assertAlmostEqual(containment(inner, outer), 1.0)
        self.assertLess(inner.iou(outer), 0.02)


class WeaponAssociationTests(unittest.TestCase):
    def setUp(self):
        self.engine = AnalyticsEngine("cam-01", AnalyticsConfig())

    def test_weapon_on_person_is_armed_person(self):
        events = self.engine.update(
            [person((100, 200, 250, 600)), handgun((150, 300, 175, 320))], now=1000.0
        )
        types = {e.type for e in events}
        self.assertIn("armed_person", types)
        self.assertNotIn("weapon_detected", types)

    def test_weapon_alone_is_weapon_detected(self):
        events = self.engine.update([handgun((10, 10, 40, 30))], now=1000.0)
        self.assertEqual([e.type for e in events], ["weapon_detected"])

    def test_weapon_far_from_person_is_not_associated(self):
        events = self.engine.update(
            [person((100, 200, 250, 600)), handgun((800, 50, 830, 70))], now=1000.0
        )
        self.assertEqual([e.type for e in events], ["weapon_detected"])

    def test_event_carries_the_detections_that_caused_it(self):
        events = self.engine.update(
            [person((100, 200, 250, 600)), handgun((150, 300, 175, 320), 0.77)],
            now=1000.0,
        )
        self.assertEqual(len(events[0].detections), 2)
        self.assertAlmostEqual(events[0].confidence, 0.9)


class HazardTests(unittest.TestCase):
    def setUp(self):
        self.engine = AnalyticsEngine("cam-01", AnalyticsConfig())

    def test_fire_and_smoke_are_separate_events(self):
        detections = [
            Detection("fire", "fire", 0.7, (0, 0, 50, 50)),
            Detection("fire", "smoke", 0.6, (60, 0, 110, 50)),
        ]
        types = {e.type for e in self.engine.update(detections, now=1.0)}
        self.assertEqual(types, {"fire_detected", "smoke_detected"})

    def test_labels_are_matched_case_insensitively(self):
        detections = [Detection("weapon", "HANDGUN", 0.9, (0, 0, 20, 20))]
        self.assertEqual(self.engine.update(detections, now=1.0)[0].type,
                         "weapon_detected")


class LoiteringTests(unittest.TestCase):
    def setUp(self):
        self.config = AnalyticsConfig(loiter_seconds=10.0, loiter_radius_px=80.0)
        self.engine = AnalyticsEngine("cam-01", self.config)

    def test_stationary_person_loiters(self):
        box = (100, 200, 200, 500)
        self.assertEqual(self.engine.update([person(box)], now=0.0), [])
        events = self.engine.update([person(box)], now=11.0)
        self.assertEqual([e.type for e in events], ["loitering"])

    def test_loitering_is_reported_once_per_dwell(self):
        box = (100, 200, 200, 500)
        self.engine.update([person(box)], now=0.0)
        self.engine.update([person(box)], now=11.0)
        self.assertEqual(self.engine.update([person(box)], now=12.0), [])

    def test_person_walking_through_does_not_loiter(self):
        for step in range(12):
            # 100 px per second: well beyond the 80 px anchor radius each frame.
            x = 100 + step * 100
            self.engine.update([person((x, 200, x + 100, 500))], now=float(step))
        events = self.engine.update([person((1400, 200, 1500, 500))], now=12.0)
        self.assertEqual(events, [])

    def test_tracks_expire_after_the_timeout(self):
        self.engine.update([person((100, 200, 200, 500))], now=0.0)
        self.assertEqual(len(self.engine.tracks), 1)
        self.engine.update([], now=self.config.track_timeout_seconds + 1)
        self.assertEqual(len(self.engine.tracks), 0)

    def test_two_people_are_tracked_separately(self):
        self.engine.update(
            [person((100, 200, 200, 500)), person((800, 200, 900, 500))], now=0.0
        )
        self.assertEqual(len(self.engine.tracks), 2)


if __name__ == "__main__":
    unittest.main()
