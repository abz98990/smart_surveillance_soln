"""Turns per-frame detections into events, using state across frames."""

import itertools
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    type: str
    camera_id: str
    detail: str
    at: float
    detections: tuple = ()

    @property
    def confidence(self):
        return max((d.confidence for d in self.detections), default=0.0)


@dataclass
class Track:
    id: int
    centroid: tuple
    first_seen: float
    last_seen: float
    # Dwell is measured from where the track settled, not from first sight, so
    # someone walking through never counts as loitering.
    anchor: tuple = (0.0, 0.0)
    anchor_since: float = 0.0
    box: tuple = (0, 0, 0, 0)
    loiter_reported: bool = False

    def dwell_seconds(self, now):
        return now - self.anchor_since


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def containment(inner, outer):
    """How much of `inner` sits inside `outer`.

    Used instead of IoU because a handgun box is a tiny fraction of a person
    box - their IoU is near zero even when the gun is in the person's hands.
    """
    ax1, ay1, ax2, ay2 = inner.box
    bx1, by1, bx2, by2 = outer.box
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0 or inner.area == 0:
        return 0.0
    return inter / inner.area


class AnalyticsEngine:
    """One per camera. Feed it every processed frame."""

    WEAPON_LABELS = {"handgun", "gun", "pistol", "rifle", "weapon", "knife"}
    FIRE_LABELS = {"fire", "flame"}
    SMOKE_LABELS = {"smoke"}
    PERSON_LABELS = {"person", "people"}

    def __init__(self, camera_id, config):
        self.camera_id = camera_id
        self.config = config
        self.tracks = {}
        self._ids = itertools.count(1)

    @classmethod
    def _is(cls, detection, labels):
        return detection.label.strip().lower() in labels

    def _split(self, detections):
        people, weapons, fires, smokes = [], [], [], []
        for d in detections:
            if self._is(d, self.PERSON_LABELS):
                people.append(d)
            elif self._is(d, self.WEAPON_LABELS):
                weapons.append(d)
            elif self._is(d, self.FIRE_LABELS):
                fires.append(d)
            elif self._is(d, self.SMOKE_LABELS):
                smokes.append(d)
        return people, weapons, fires, smokes

    def _update_tracks(self, people, now):
        """Greedy nearest-centroid matching."""
        unmatched = list(self.tracks.values())
        for detection in people:
            centroid = detection.centroid
            best, best_distance = None, self.config.loiter_radius_px
            for track in unmatched:
                distance = _distance(track.centroid, centroid)
                if distance <= best_distance:
                    best, best_distance = track, distance

            if best is None:
                track_id = next(self._ids)
                self.tracks[track_id] = Track(
                    id=track_id,
                    centroid=centroid,
                    first_seen=now,
                    last_seen=now,
                    anchor=centroid,
                    anchor_since=now,
                    box=detection.box,
                )
                continue

            unmatched.remove(best)
            best.centroid = centroid
            best.last_seen = now
            best.box = detection.box
            if _distance(best.anchor, centroid) > self.config.loiter_radius_px:
                best.anchor = centroid
                best.anchor_since = now
                best.loiter_reported = False

        stale = [
            track_id
            for track_id, track in self.tracks.items()
            if now - track.last_seen > self.config.track_timeout_seconds
        ]
        for track_id in stale:
            del self.tracks[track_id]

    def update(self, detections, now):
        """Events raised by this frame. Suppressing repeats is AlertManager's job."""
        people, weapons, fires, smokes = self._split(detections)
        self._update_tracks(people, now)
        events = []

        for weapon in weapons:
            carrier = None
            best_overlap = self.config.weapon_person_overlap
            for person in people:
                overlap = containment(weapon, person)
                if overlap >= best_overlap:
                    carrier, best_overlap = person, overlap

            if carrier is not None:
                events.append(
                    Event(
                        type="armed_person",
                        camera_id=self.camera_id,
                        detail="{} ({:.0%}) associated with a person".format(
                            weapon.label, weapon.confidence
                        ),
                        at=now,
                        detections=(weapon, carrier),
                    )
                )
            else:
                events.append(
                    Event(
                        type="weapon_detected",
                        camera_id=self.camera_id,
                        detail="{} ({:.0%}), no person associated".format(
                            weapon.label, weapon.confidence
                        ),
                        at=now,
                        detections=(weapon,),
                    )
                )

        for fire in fires:
            events.append(
                Event(
                    type="fire_detected",
                    camera_id=self.camera_id,
                    detail="fire ({:.0%})".format(fire.confidence),
                    at=now,
                    detections=(fire,),
                )
            )

        for smoke in smokes:
            events.append(
                Event(
                    type="smoke_detected",
                    camera_id=self.camera_id,
                    detail="smoke ({:.0%})".format(smoke.confidence),
                    at=now,
                    detections=(smoke,),
                )
            )

        for track in self.tracks.values():
            if track.loiter_reported:
                continue
            if track.dwell_seconds(now) >= self.config.loiter_seconds:
                track.loiter_reported = True
                events.append(
                    Event(
                        type="loitering",
                        camera_id=self.camera_id,
                        detail="person stationary for {:.0f}s".format(
                            track.dwell_seconds(now)
                        ),
                        at=now,
                    )
                )

        return events
