"""Dashboard routes, against a stubbed service - no camera or OpenCV needed."""

import tempfile
import unittest
from pathlib import Path

from surveillance.alerts import AlertManager
from surveillance.config import AlertRule, AppConfig, CameraConfig, DetectorConfig, StorageConfig
from surveillance.storage import EventStore
from surveillance.web import create_app


class StubDetectors:
    def __init__(self):
        self._conf = {"weapon": 0.4, "fire": 0.5}

    def confidence(self, detector_id):
        return self._conf.get(detector_id, 0.4)

    def set_confidence(self, detector_id, value):
        self._conf[detector_id] = float(value)
        return self._conf[detector_id]


class StubService:
    def __init__(self, alerts, store):
        self.detectors = StubDetectors()
        self.alerts = alerts
        self.store = store

    def buffer(self, camera_id):
        return None if camera_id != "cam-01" else StubBuffer()

    @property
    def status(self):
        return {
            "uptime_seconds": 12.0,
            "unacknowledged": self.store.unacknowledged_count(),
            "cameras": [{
                "id": "cam-01", "name": "Primary USB camera", "source": "0",
                "network": False, "live": True, "fps": 9.4, "frames": 812,
                "tracks": 2, "error": "",
            }],
        }


class StubBuffer:
    def wait_for_frame(self, timeout=2.0):
        return b"\xff\xd8\xff\xd9"


class WebTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.config = AppConfig(
            cameras=(CameraConfig(id="cam-01", name="Primary USB camera", source=0),),
            detectors=(
                DetectorConfig(id="weapon", weights="weights_gun/best.pt", conf=0.40),
                DetectorConfig(id="fire", weights="weights_fire/best.pt", conf=0.50),
            ),
            rules=(
                AlertRule(event="weapon_detected", severity="critical",
                          cooldown_seconds=30, min_consecutive_frames=2,
                          channels=("desktop", "email")),
                AlertRule(event="loitering", severity="warning",
                          cooldown_seconds=120, min_consecutive_frames=1,
                          channels=("desktop",)),
            ),
            storage=StorageConfig(),
        )
        self.store = EventStore(self.config.storage, root=self.root)
        self.alerts = AlertManager(rules=self.config.rules, store=self.store)
        self.service = StubService(self.alerts, self.store)
        app = create_app(self.service, self.store, self.config)
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        self._tmp.cleanup()

    def seed(self, **kwargs):
        params = dict(camera_id="cam-01", event_type="weapon_detected",
                      severity="critical", detail="Handgun (81%)", confidence=0.81)
        params.update(kwargs)
        return self.store.record(**params)


class PageTests(WebTestCase):
    def test_dashboard_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Primary USB camera", response.data)

    def test_dashboard_shows_logged_alerts(self):
        self.seed()
        response = self.client.get("/")
        self.assertIn(b"Handgun (81%)", response.data)
        self.assertIn(b"weapon detected", response.data)

    def test_dashboard_renders_with_an_empty_log(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Nothing logged yet", response.data)

    def test_event_log_renders(self):
        self.seed()
        response = self.client.get("/events")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Event log", response.data)

    def test_event_log_filters_by_severity(self):
        self.seed(severity="critical", detail="critical one")
        self.seed(severity="warning", event_type="loitering", detail="warning one")
        response = self.client.get("/events?severity=warning")
        self.assertIn(b"warning one", response.data)
        self.assertNotIn(b"critical one", response.data)

    def test_event_log_filters_by_camera(self):
        self.seed(camera_id="cam-01", detail="on one")
        self.seed(camera_id="cam-02", detail="on two")
        response = self.client.get("/events?camera=cam-02")
        self.assertIn(b"on two", response.data)
        self.assertNotIn(b"on one", response.data)

    def test_settings_renders_and_shows_active_thresholds(self):
        response = self.client.get("/settings")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"0.50", response.data)      # fire threshold
        self.assertIn(b"not configured", response.data)  # email channel is off


class ActionTests(WebTestCase):
    def test_acknowledging_an_alert(self):
        alert_id = self.seed()
        self.assertEqual(self.store.unacknowledged_count(), 1)
        response = self.client.post("/alerts/{}/ack".format(alert_id))
        self.assertIn(response.status_code, (302, 303))
        self.assertEqual(self.store.unacknowledged_count(), 0)

    def test_acknowledging_via_json(self):
        alert_id = self.seed()
        response = self.client.post(
            "/alerts/{}/ack".format(alert_id),
            headers={"Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

    def test_settings_updates_a_detector_threshold(self):
        self.client.post("/settings", data={"conf_fire": "0.65"})
        self.assertAlmostEqual(self.service.detectors.confidence("fire"), 0.65)

    def test_settings_updates_an_alert_rule(self):
        self.client.post("/settings", data={
            "cooldown_weapon_detected": "90", "frames_weapon_detected": "5"
        })
        rule = self.alerts.rules["weapon_detected"]
        self.assertEqual(rule.cooldown_seconds, 90)
        self.assertEqual(rule.min_consecutive_frames, 5)

    def test_settings_ignores_a_nonsense_threshold(self):
        before = self.service.detectors.confidence("fire")
        self.client.post("/settings", data={"conf_fire": "not-a-number"})
        self.assertEqual(self.service.detectors.confidence("fire"), before)


class ApiTests(WebTestCase):
    def test_status_endpoint(self):
        payload = self.client.get("/api/status").get_json()
        self.assertEqual(payload["cameras"][0]["id"], "cam-01")

    def test_alerts_endpoint(self):
        self.seed()
        payload = self.client.get("/api/alerts").get_json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["event"], "weapon_detected")
        self.assertAlmostEqual(payload[0]["confidence"], 0.81)


class MediaTests(WebTestCase):
    def test_stream_for_an_unknown_camera_is_404(self):
        self.assertEqual(self.client.get("/stream/nope").status_code, 404)

    def test_snapshot_serves_a_stored_file(self):
        self.seed()
        self.store.record(camera_id="cam-01", event_type="weapon_detected",
                          severity="critical", detail="x", confidence=0.9,
                          snapshot_bytes=b"\xff\xd8jpeg-bytes")
        name = [a.snapshot for a in self.store.recent() if a.snapshot][0]
        response = self.client.get("/snapshot/" + name)
        self.assertEqual(response.status_code, 200)
        response.close()   # the test client holds the file open otherwise

    def test_snapshot_cannot_escape_its_directory(self):
        for attempt in ("../../config.yaml", "..%2f..%2fconfig.yaml"):
            response = self.client.get("/snapshot/" + attempt)
            self.assertIn(response.status_code, (400, 403, 404),
                          "path traversal was not blocked: " + attempt)


if __name__ == "__main__":
    unittest.main()
