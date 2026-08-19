"""Configuration loading for the Smart Surveillance System.

Everything the operator can tune lives in ``config.yaml``; everything secret
lives in the environment (see ``.env.example``).  Nothing sensitive is ever
written to the config file, so the file is safe to commit.
"""

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@dataclass(frozen=True)
class CameraConfig:
    """One video source.

    ``source`` is passed straight to ``cv2.VideoCapture``: an integer for a
    local USB device, or a string for a file path or an RTSP/HTTP URL, which
    is how the Wi-Fi cameras are attached.
    """

    id: str
    name: str
    source: object = 0
    enabled: bool = True
    # Frames per second to *process*. The camera is still read at its native
    # rate; surplus frames are dropped so a slow model cannot back up the queue.
    process_fps: float = 10.0

    @property
    def is_network_source(self):
        return isinstance(self.source, str) and "://" in self.source


@dataclass(frozen=True)
class DetectorConfig:
    """One YOLO model and how its boxes are drawn."""

    id: str
    weights: str
    conf: float = 0.4
    enabled: bool = True
    # BGR, because that is what OpenCV draws with.
    colour: tuple = (0, 225, 0)
    # Restrict to these class ids; empty means "keep everything the model emits".
    keep_classes: tuple = ()
    # Per-class confidence overrides, keyed by lower-cased class name. Classes
    # within one model rarely perform alike; see docs/MODEL_CARD.md.
    class_conf: tuple = ()

    @property
    def class_conf_map(self):
        return {str(k).lower(): float(v) for k, v in self.class_conf}


@dataclass(frozen=True)
class AlertRule:
    """Maps an analytics event type onto a severity and a cooldown."""

    event: str
    severity: str = "warning"
    # Suppress repeats of the same event on the same camera for this long.
    cooldown_seconds: float = 30.0
    # Require the condition to hold for this many consecutive processed frames
    # before firing, which is what stops single-frame false positives paging
    # an operator.
    min_consecutive_frames: int = 3
    channels: tuple = ("desktop",)


@dataclass(frozen=True)
class AnalyticsConfig:
    # A person whose centroid stays inside ``loiter_radius_px`` for longer than
    # this many seconds is loitering.
    loiter_seconds: float = 20.0
    loiter_radius_px: float = 80.0
    # Tracks are forgotten this long after they were last seen.
    track_timeout_seconds: float = 3.0
    # Minimum fraction of a weapon box that must fall inside a person box
    # before the two are treated as "this person is carrying it".
    weapon_person_overlap: float = 0.30


@dataclass(frozen=True)
class StorageConfig:
    db_path: str = "data/surveillance.db"
    snapshot_dir: str = "data/snapshots"
    # Only frames attached to an alert are written to disk. Everything else is
    # discarded as soon as it has been processed, which is the retention
    # behaviour the ethics section commits to.
    save_snapshots: bool = True
    retention_days: int = 30


@dataclass(frozen=True)
class EmailConfig:
    """Read from the environment only - never from config.yaml."""

    host: str = ""
    port: int = 587
    username: str = ""
    password: str = field(default="", repr=False)
    sender: str = ""
    recipients: tuple = ()
    use_tls: bool = True

    @property
    def is_configured(self):
        return bool(self.host and self.username and self.password and self.recipients)

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        raw_recipients = env.get("SSS_ALERT_RECIPIENTS", "")
        recipients = tuple(r.strip() for r in raw_recipients.split(",") if r.strip())
        username = env.get("SSS_SMTP_USER", "").strip()
        try:
            port = int(env.get("SSS_SMTP_PORT", "587"))
        except ValueError:
            port = 587
        return cls(
            host=env.get("SSS_SMTP_HOST", "").strip(),
            port=port,
            username=username,
            password=env.get("SSS_SMTP_PASSWORD", ""),
            sender=env.get("SSS_SMTP_FROM", "").strip() or username,
            recipients=recipients,
        )


@dataclass(frozen=True)
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    # JPEG quality for the dashboard stream. Lower means less bandwidth.
    stream_quality: int = 75

    @classmethod
    def from_env(cls, base=None, env=None):
        env = os.environ if env is None else env
        base = base or cls()
        try:
            port = int(env.get("SSS_WEB_PORT", base.port))
        except ValueError:
            port = base.port
        return replace(base, host=env.get("SSS_WEB_HOST", base.host), port=port)


@dataclass(frozen=True)
class AppConfig:
    cameras: tuple = ()
    detectors: tuple = ()
    rules: tuple = ()
    analytics: AnalyticsConfig = AnalyticsConfig()
    storage: StorageConfig = StorageConfig()
    email: EmailConfig = EmailConfig()
    web: WebConfig = WebConfig()

    def detector(self, detector_id):
        for d in self.detectors:
            if d.id == detector_id:
                return d
        return None

    def rule(self, event):
        for r in self.rules:
            if r.event == event:
                return r
        return None

    @property
    def enabled_cameras(self):
        return tuple(c for c in self.cameras if c.enabled)

    @property
    def enabled_detectors(self):
        return tuple(d for d in self.detectors if d.enabled)


def _load_dotenv(path):
    """Minimal .env reader so the project has no python-dotenv dependency.

    Values already present in the real environment win, so an operator can
    always override the file from the shell.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path=None, load_env=True):
    """Build an :class:`AppConfig` from ``config.yaml`` plus the environment."""
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    if load_env:
        _load_dotenv(PROJECT_ROOT / ".env")

    raw = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    cameras = tuple(
        CameraConfig(
            id=str(c["id"]),
            name=c.get("name", str(c["id"])),
            source=c.get("source", 0),
            enabled=bool(c.get("enabled", True)),
            process_fps=float(c.get("process_fps", 10.0)),
        )
        for c in raw.get("cameras", [])
    )

    detectors = tuple(
        DetectorConfig(
            id=str(d["id"]),
            weights=d["weights"],
            conf=float(d.get("conf", 0.4)),
            enabled=bool(d.get("enabled", True)),
            colour=tuple(d.get("colour", (0, 225, 0))),
            keep_classes=tuple(d.get("keep_classes", ())),
            class_conf=tuple(sorted((d.get("class_conf") or {}).items())),
        )
        for d in raw.get("detectors", [])
    )

    rules = tuple(
        AlertRule(
            event=str(r["event"]),
            severity=r.get("severity", "warning"),
            cooldown_seconds=float(r.get("cooldown_seconds", 30.0)),
            min_consecutive_frames=int(r.get("min_consecutive_frames", 3)),
            channels=tuple(r.get("channels", ("desktop",))),
        )
        for r in raw.get("rules", [])
    )

    analytics = AnalyticsConfig(**(raw.get("analytics") or {}))
    storage = StorageConfig(**(raw.get("storage") or {}))
    web = WebConfig.from_env(WebConfig(**(raw.get("web") or {})))

    return AppConfig(
        cameras=cameras,
        detectors=detectors,
        rules=rules,
        analytics=analytics,
        storage=storage,
        email=EmailConfig.from_env(),
        web=web,
    )
