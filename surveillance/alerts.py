"""Decides which events reach an operator, and delivers them off-thread."""

import logging
import queue
import threading
import time
from dataclasses import dataclass, replace

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Alert:
    event_type: str
    camera_id: str
    camera_name: str
    severity: str
    detail: str
    confidence: float
    at: float
    channels: tuple = ()
    record_id: int = 0

    @property
    def title(self):
        return "{}: {}".format(self.severity.upper(), self.event_type.replace("_", " "))

    @property
    def message(self):
        return "{} on {} at {}".format(
            self.detail, self.camera_name,
            time.strftime("%H:%M:%S", time.localtime(self.at)),
        )


class AlertManager:
    def __init__(self, rules, store=None, channels=None, camera_names=None):
        self.rules = {r.event: r for r in rules}
        self.store = store
        self.channels = channels or {}
        self.camera_names = camera_names or {}
        self._streaks = {}
        self._last_fired = {}
        self._queue = queue.Queue(maxsize=200)
        self._worker = None
        self._stop = threading.Event()

    def start(self):
        if self._worker is not None:
            return
        self._stop.clear()
        self._worker = threading.Thread(
            target=self._dispatch_loop, name="alert-dispatch", daemon=True
        )
        self._worker.start()

    def stop(self, timeout=5.0):
        if self._worker is None:
            return
        self._stop.set()
        self._queue.put(None)
        self._worker.join(timeout=timeout)
        self._worker = None

    def submit(self, events, camera_id, now=None, snapshot=None):
        """Call once per processed frame, including quiet ones, so streaks for
        events that have stopped get reset. Returns the alerts that fired.

        `snapshot` is only called when an alert fires, so quiet frames pay
        nothing for JPEG encoding.
        """
        now = time.time() if now is None else now
        seen = {}
        for event in events:
            if event.type not in seen or event.confidence > seen[event.type].confidence:
                seen[event.type] = event

        for key in list(self._streaks):
            if key[0] == camera_id and key[1] not in seen:
                self._streaks[key] = 0

        fired = []
        for event_type, event in seen.items():
            rule = self.rules.get(event_type)
            if rule is None:
                continue

            key = (camera_id, event_type)
            self._streaks[key] = self._streaks.get(key, 0) + 1
            if self._streaks[key] < rule.min_consecutive_frames:
                continue

            last = self._last_fired.get(key)
            if last is not None and (now - last) < rule.cooldown_seconds:
                continue

            self._last_fired[key] = now
            alert = Alert(
                event_type=event_type,
                camera_id=camera_id,
                camera_name=self.camera_names.get(camera_id, camera_id),
                severity=rule.severity,
                detail=event.detail,
                confidence=event.confidence,
                at=now,
                channels=rule.channels,
            )
            fired.append(self._persist_and_queue(alert, snapshot))

        return fired

    def _persist_and_queue(self, alert, snapshot):
        record_id = 0
        if self.store is not None:
            snapshot_bytes = None
            if snapshot is not None:
                try:
                    snapshot_bytes = snapshot()
                except Exception:
                    log.exception("snapshot capture failed for %s", alert.event_type)
            record_id = self.store.record(
                camera_id=alert.camera_id,
                event_type=alert.event_type,
                severity=alert.severity,
                detail=alert.detail,
                confidence=alert.confidence,
                at=alert.at,
                snapshot_bytes=snapshot_bytes,
            )

        alert = replace(alert, record_id=record_id)
        try:
            self._queue.put_nowait(alert)
        except queue.Full:
            # Better to drop a notification than stall a camera; it is in the
            # database either way.
            log.warning("alert dispatch queue full, dropped %s", alert.event_type)
        return alert

    def _dispatch_loop(self):
        while not self._stop.is_set():
            try:
                alert = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if alert is None:
                break
            for name in alert.channels:
                channel = self.channels.get(name)
                if channel is None:
                    log.warning("no channel named %r configured", name)
                    continue
                try:
                    channel.send(alert)
                except Exception:
                    log.exception("channel %s failed to send %s", name, alert.event_type)

    def cooldown_remaining(self, camera_id, event_type, now=None):
        now = time.time() if now is None else now
        rule = self.rules.get(event_type)
        last = self._last_fired.get((camera_id, event_type))
        if rule is None or last is None:
            return 0.0
        return max(0.0, rule.cooldown_seconds - (now - last))
