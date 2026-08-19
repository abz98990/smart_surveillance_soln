"""Alert debouncing, cooldown and dispatch.

These are the tests that pin the alert-fatigue behaviour the report commits to:
a detection on a single frame must not notify anyone, and a persistent threat
must not notify anyone more than once per cooldown.
"""

import time
import unittest

from surveillance.alerts import AlertManager
from surveillance.analytics import Event
from surveillance.config import AlertRule


class RecordingChannel:
    name = "recording"

    def __init__(self):
        self.sent = []

    def send(self, alert):
        self.sent.append(alert)


class ExplodingChannel:
    name = "exploding"

    def send(self, alert):
        raise RuntimeError("channel is down")


def weapon_event(at=0.0, confidence=0.8):
    return Event(type="weapon_detected", camera_id="cam-01",
                 detail="Handgun ({:.0%})".format(confidence), at=at)


class DebounceTests(unittest.TestCase):
    def setUp(self):
        self.rule = AlertRule(event="weapon_detected", severity="critical",
                              cooldown_seconds=30.0, min_consecutive_frames=3)
        self.manager = AlertManager(rules=[self.rule])

    def test_single_frame_does_not_fire(self):
        self.assertEqual(self.manager.submit([weapon_event()], "cam-01", now=0.0), [])

    def test_fires_on_the_nth_consecutive_frame(self):
        self.assertEqual(self.manager.submit([weapon_event()], "cam-01", now=0.0), [])
        self.assertEqual(self.manager.submit([weapon_event()], "cam-01", now=0.1), [])
        fired = self.manager.submit([weapon_event()], "cam-01", now=0.2)
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0].event_type, "weapon_detected")
        self.assertEqual(fired[0].severity, "critical")

    def test_a_quiet_frame_resets_the_streak(self):
        self.manager.submit([weapon_event()], "cam-01", now=0.0)
        self.manager.submit([weapon_event()], "cam-01", now=0.1)
        self.manager.submit([], "cam-01", now=0.2)          # nothing detected
        self.assertEqual(self.manager.submit([weapon_event()], "cam-01", now=0.3), [])

    def test_streaks_are_tracked_per_camera(self):
        for now in (0.0, 0.1):
            self.manager.submit([weapon_event()], "cam-01", now=now)
        # cam-02 starts its own streak; it must not inherit cam-01's.
        self.assertEqual(self.manager.submit([weapon_event()], "cam-02", now=0.2), [])

    def test_a_quiet_frame_on_one_camera_leaves_the_other_alone(self):
        self.manager.submit([weapon_event()], "cam-01", now=0.0)
        self.manager.submit([weapon_event()], "cam-01", now=0.1)
        self.manager.submit([], "cam-02", now=0.15)
        self.assertEqual(len(self.manager.submit([weapon_event()], "cam-01", now=0.2)), 1)


class CooldownTests(unittest.TestCase):
    def setUp(self):
        self.manager = AlertManager(rules=[
            AlertRule(event="weapon_detected", severity="critical",
                      cooldown_seconds=30.0, min_consecutive_frames=1)
        ])

    def test_repeats_are_suppressed_within_the_cooldown(self):
        self.assertEqual(len(self.manager.submit([weapon_event()], "cam-01", now=0.0)), 1)
        for now in (1.0, 5.0, 29.9):
            self.assertEqual(self.manager.submit([weapon_event()], "cam-01", now=now), [])

    def test_fires_again_once_the_cooldown_expires(self):
        self.manager.submit([weapon_event()], "cam-01", now=0.0)
        self.assertEqual(len(self.manager.submit([weapon_event()], "cam-01", now=30.1)), 1)

    def test_ten_seconds_at_ten_fps_produces_one_alert_not_a_hundred(self):
        fired = []
        for frame in range(100):
            fired += self.manager.submit([weapon_event()], "cam-01", now=frame * 0.1)
        self.assertEqual(len(fired), 1)

    def test_cooldown_remaining_is_reported(self):
        self.manager.submit([weapon_event()], "cam-01", now=100.0)
        self.assertAlmostEqual(
            self.manager.cooldown_remaining("cam-01", "weapon_detected", now=110.0), 20.0
        )


class SelectionTests(unittest.TestCase):
    def test_unconfigured_events_are_ignored(self):
        manager = AlertManager(rules=[
            AlertRule(event="weapon_detected", min_consecutive_frames=1)
        ])
        loiter = Event(type="loitering", camera_id="cam-01", detail="", at=0.0)
        self.assertEqual(manager.submit([loiter], "cam-01", now=0.0), [])

    def test_highest_confidence_instance_wins(self):
        manager = AlertManager(rules=[
            AlertRule(event="weapon_detected", min_consecutive_frames=1)
        ])
        events = [
            Event("weapon_detected", "cam-01", "low", 0.0,
                  detections=(_D(0.30),)),
            Event("weapon_detected", "cam-01", "high", 0.0,
                  detections=(_D(0.95),)),
        ]
        fired = manager.submit(events, "cam-01", now=0.0)
        self.assertEqual(fired[0].detail, "high")

    def test_snapshot_is_only_taken_when_an_alert_fires(self):
        calls = []
        store = _RecordingStore()
        manager = AlertManager(
            rules=[AlertRule(event="weapon_detected", min_consecutive_frames=2)],
            store=store,
        )

        def snapshot():
            calls.append(1)
            return b"jpeg"

        manager.submit([weapon_event()], "cam-01", now=0.0, snapshot=snapshot)
        self.assertEqual(calls, [])          # debounced, no encode
        manager.submit([weapon_event()], "cam-01", now=0.1, snapshot=snapshot)
        self.assertEqual(len(calls), 1)      # fired, encoded once
        self.assertEqual(store.records[0]["snapshot_bytes"], b"jpeg")


class DispatchTests(unittest.TestCase):
    def test_alerts_reach_their_channels(self):
        channel = RecordingChannel()
        manager = AlertManager(
            rules=[AlertRule(event="weapon_detected", min_consecutive_frames=1,
                             channels=("recording",))],
            channels={"recording": channel},
        )
        manager.start()
        try:
            manager.submit([weapon_event()], "cam-01", now=0.0)
            deadline = time.time() + 2
            while not channel.sent and time.time() < deadline:
                time.sleep(0.01)
        finally:
            manager.stop()
        self.assertEqual(len(channel.sent), 1)
        self.assertEqual(channel.sent[0].camera_id, "cam-01")

    def test_a_failing_channel_does_not_stop_the_others(self):
        good = RecordingChannel()
        manager = AlertManager(
            rules=[AlertRule(event="weapon_detected", min_consecutive_frames=1,
                             channels=("exploding", "recording"))],
            channels={"exploding": ExplodingChannel(), "recording": good},
        )
        manager.start()
        try:
            manager.submit([weapon_event()], "cam-01", now=0.0)
            deadline = time.time() + 2
            while not good.sent and time.time() < deadline:
                time.sleep(0.01)
        finally:
            manager.stop()
        self.assertEqual(len(good.sent), 1)

    def test_submit_returns_immediately_even_with_a_slow_channel(self):
        class SlowChannel:
            def send(self, alert):
                time.sleep(1.0)

        manager = AlertManager(
            rules=[AlertRule(event="weapon_detected", min_consecutive_frames=1,
                             channels=("slow",))],
            channels={"slow": SlowChannel()},
        )
        manager.start()
        try:
            started = time.perf_counter()
            manager.submit([weapon_event()], "cam-01", now=0.0)
            elapsed = time.perf_counter() - started
        finally:
            manager.stop(timeout=2)
        # The old code slept 1s inline per alerting frame. This must not.
        self.assertLess(elapsed, 0.2)


class _D:
    """Minimal stand-in for a Detection, for confidence comparisons."""

    def __init__(self, confidence):
        self.confidence = confidence


class _RecordingStore:
    def __init__(self):
        self.records = []

    def record(self, **kwargs):
        self.records.append(kwargs)
        return len(self.records)


if __name__ == "__main__":
    unittest.main()
