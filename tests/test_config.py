"""Configuration loading, and the guarantee that no secret lives in a file."""

import unittest
from pathlib import Path

import yaml

from surveillance.config import (
    PROJECT_ROOT,
    AppConfig,
    EmailConfig,
    WebConfig,
    load_config,
)
from surveillance.geometry import centre_offset, clamp_text_origin, fit_size, grid_shape


class ShippedConfigTests(unittest.TestCase):
    """The config.yaml that ships with the project must actually work."""

    def setUp(self):
        self.config = load_config(load_env=False)

    def test_it_loads(self):
        self.assertIsInstance(self.config, AppConfig)

    def test_every_enabled_detector_has_weights_on_disk(self):
        for detector in self.config.enabled_detectors:
            path = PROJECT_ROOT / detector.weights
            self.assertTrue(path.exists(), "missing weights: " + detector.weights)

    def test_detectors_use_the_best_checkpoint_not_the_last(self):
        for detector in self.config.detectors:
            self.assertTrue(detector.weights.endswith("best.pt"), detector.weights)

    def test_at_least_one_camera_is_enabled(self):
        self.assertTrue(self.config.enabled_cameras)

    def test_every_rule_targets_a_known_event(self):
        known = {"weapon_detected", "armed_person", "fire_detected",
                 "smoke_detected", "loitering"}
        for rule in self.config.rules:
            self.assertIn(rule.event, known)

    def test_every_rule_debounces(self):
        for rule in self.config.rules:
            self.assertGreaterEqual(rule.min_consecutive_frames, 1)
            self.assertGreater(rule.cooldown_seconds, 0)

    def test_fire_is_held_to_a_stricter_threshold(self):
        """The fire model validates at precision 0.537, so it must not run at
        the 0.25 library default the original scripts used."""
        fire = self.config.detector("fire")
        self.assertIsNotNone(fire)
        self.assertGreaterEqual(fire.conf, 0.5)

    def test_a_network_camera_is_recognised_as_one(self):
        network = [c for c in self.config.cameras if c.is_network_source]
        self.assertTrue(network, "config should demonstrate a Wi-Fi/RTSP source")


class SecretHygieneTests(unittest.TestCase):
    def test_config_yaml_declares_no_credential_keys(self):
        """Comments may discuss secrets; no *key* may hold one."""
        raw = (PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8")
        keys = []
        for line in raw.splitlines():
            line = line.split("#", 1)[0].strip().lstrip("- ")
            if ":" in line:
                keys.append(line.split(":", 1)[0].strip().lower())
        for smell in ("password", "passwd", "api_key", "apikey", "secret",
                      "token", "credential"):
            self.assertNotIn(smell, keys, "config.yaml must never carry secrets")

    def test_no_tracked_python_file_hardcodes_an_smtp_login(self):
        offenders = []
        for path in PROJECT_ROOT.rglob("*.py"):
            if any(part in {"venv", ".venv", "__pycache__"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if ".login(" in text and "self.config.username" not in text:
                offenders.append(str(path.relative_to(PROJECT_ROOT)))
        self.assertEqual(offenders, [])

    def test_env_is_ignored_by_git(self):
        ignored = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env", ignored)

    def test_email_is_disabled_when_the_environment_is_empty(self):
        config = EmailConfig.from_env(env={})
        self.assertFalse(config.is_configured)

    def test_email_reads_the_environment(self):
        config = EmailConfig.from_env(env={
            "SSS_SMTP_HOST": "smtp.example.com",
            "SSS_SMTP_USER": "alerts@example.com",
            "SSS_SMTP_PASSWORD": "secret",
            "SSS_ALERT_RECIPIENTS": "a@example.com, b@example.com",
        })
        self.assertTrue(config.is_configured)
        self.assertEqual(config.recipients, ("a@example.com", "b@example.com"))
        self.assertEqual(config.sender, "alerts@example.com")

    def test_password_is_not_in_the_repr(self):
        config = EmailConfig(host="h", username="u", password="hunter2",
                             recipients=("x@y.z",))
        self.assertNotIn("hunter2", repr(config))


class EnvOverrideTests(unittest.TestCase):
    def test_web_host_and_port_come_from_the_environment(self):
        config = WebConfig.from_env(WebConfig(), env={
            "SSS_WEB_HOST": "0.0.0.0", "SSS_WEB_PORT": "9001"
        })
        self.assertEqual((config.host, config.port), ("0.0.0.0", 9001))

    def test_a_bad_port_falls_back_to_the_default(self):
        config = WebConfig.from_env(WebConfig(port=8000), env={"SSS_WEB_PORT": "abc"})
        self.assertEqual(config.port, 8000)


class GeometryTests(unittest.TestCase):
    def test_aspect_ratio_is_preserved(self):
        # A 4:3 frame into a 16:9 panel must letterbox, not stretch.
        width, height = fit_size(640, 480, 1280, 720)
        self.assertEqual((width, height), (960, 720))
        self.assertAlmostEqual(width / height, 640 / 480, places=2)

    def test_it_fits_inside_the_box(self):
        for box in ((1920, 1080), (300, 900), (100, 100)):
            width, height = fit_size(640, 480, *box)
            self.assertLessEqual(width, box[0])
            self.assertLessEqual(height, box[1])

    def test_degenerate_input_is_handled(self):
        self.assertEqual(fit_size(0, 480, 100, 100), (0, 0))
        self.assertEqual(fit_size(640, 480, 0, 100), (0, 0))

    def test_centring(self):
        self.assertEqual(centre_offset(960, 720, 1280, 720), (160, 0))

    def test_grid_shapes(self):
        self.assertEqual(grid_shape(1), (1, 1))
        self.assertEqual(grid_shape(2), (1, 2))
        self.assertEqual(grid_shape(4), (2, 2))
        self.assertEqual(grid_shape(5), (2, 3))
        self.assertEqual(grid_shape(0), (0, 0))

    def test_text_origin_is_pushed_inside_the_frame(self):
        # (0, 0) is the classic invisible-label bug: the baseline sits on the
        # top edge so every glyph renders above it.
        x, y = clamp_text_origin(0, 0, text_height=12)
        self.assertGreater(x, 0)
        self.assertGreaterEqual(y, 12)


class YamlSanityTests(unittest.TestCase):
    def test_config_yaml_is_valid_yaml(self):
        raw = yaml.safe_load(Path(PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))
        self.assertIn("cameras", raw)
        self.assertIn("detectors", raw)
        self.assertIn("rules", raw)


if __name__ == "__main__":
    unittest.main()
