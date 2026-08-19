"""Alert decisioning and dispatch.

Two problems are solved here.

*Alert fatigue.* A raw detector fires on every frame, so a weapon held in view
for ten seconds at 10 fps is a hundred notifications. Every event must survive
``min_consecutive_frames`` before it counts, and once it has fired the same
event on the same camera is suppressed for ``cooldown_seconds``.

*Blocking.* Sending mail or raising a toast takes anywhere from milliseconds to
seconds. Dispatch therefore runs on its own worker thread and the capture loop
never waits for it.
"""

import logging
import queue
import threading
import time
from dataclasses import dataclass, replace

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Alert:
    """An event that passed the debounce and cooldown gates."""

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

    # -- lifecycle ---------------------------------------------------------
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

    # -- decisioning -------------------------------------------------------
    def submit(self, events, camera_id, now=None, snapshot=None):
        """Offer one frame's events to the manager.

        Must be called once per processed frame, including frames that produced
        nothing, so that streaks for events which have stopped occurring are
        reset. ``snapshot`` is a zero-argument callable returning JPEG bytes; it
        is only invoked when an alert actually fires, so encoding costs nothing
        on quiet frames.

        Returns the alerts that fired on this frame.
        """
        now = time.time() if now is None else now
        seen = {}
        for event in events:
            # Keep the highest-confidence instance of each event type.
            if event.type not in seen or event.confidence > seen[event.type].confidence:
                seen[event.type] = event

        # Reset streaks for this camera's events that are absent from this frame.
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
                except Exception:  # a bad frame must not take down the loop
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
            # Dropping a notification is better than stalling the camera; the
            # alert is already in the database either way.
            log.warning("alert dispatch queue full, dropped %s", alert.event_type)
        return alert

    # -- dispatch ----------------------------------------------------------
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

    # -- introspection, used by the dashboard ------------------------------
    def cooldown_remaining(self, camera_id, event_type, now=None):
        now = time.time() if now is None else now
        rule = self.rules.get(event_type)
        last = self._last_fired.get((camera_id, event_type))
        if rule is None or last is None:
            return 0.0
        return max(0.0, rule.cooldown_seconds - (now - last))
