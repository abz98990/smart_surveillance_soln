"""Event log persistence and the snapshot retention policy."""

import tempfile
import time
import unittest
from pathlib import Path

from surveillance.config import StorageConfig
from surveillance.storage import EventStore


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = EventStore(StorageConfig(retention_days=30), root=self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def add(self, event_type="weapon_detected", severity="critical", at=None,
            snapshot=None, camera_id="cam-01"):
        return self.store.record(
            camera_id=camera_id, event_type=event_type, severity=severity,
            detail="test", confidence=0.9, at=at, snapshot_bytes=snapshot,
        )


class RecordAndReadTests(StoreTestCase):
    def test_record_returns_an_id_and_is_readable(self):
        alert_id = self.add()
        self.assertGreater(alert_id, 0)
        recent = self.store.recent()
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].event_type, "weapon_detected")
        self.assertFalse(recent[0].acknowledged)

    def test_newest_first(self):
        self.add(event_type="first", at=100.0)
        self.add(event_type="second", at=200.0)
        self.assertEqual([a.event_type for a in self.store.recent()],
                         ["second", "first"])

    def test_filter_by_camera_and_severity(self):
        self.add(camera_id="cam-01", severity="critical")
        self.add(camera_id="cam-02", severity="warning")
        self.assertEqual(len(self.store.recent(camera_id="cam-02")), 1)
        self.assertEqual(len(self.store.recent(severity="critical")), 1)
        self.assertEqual(len(self.store.recent(camera_id="cam-01",
                                               severity="warning")), 0)

    def test_limit_is_respected(self):
        for _ in range(10):
            self.add()
        self.assertEqual(len(self.store.recent(limit=3)), 3)

    def test_counts(self):
        self.add(severity="critical", event_type="weapon_detected")
        self.add(severity="critical", event_type="weapon_detected")
        self.add(severity="warning", event_type="loitering")
        self.assertEqual(self.store.counts_by_severity(),
                         {"critical": 2, "warning": 1})
        self.assertEqual(self.store.counts_by_event()["weapon_detected"], 2)

    def test_acknowledgement(self):
        alert_id = self.add()
        self.assertEqual(self.store.unacknowledged_count(), 1)
        self.store.acknowledge(alert_id)
        self.assertEqual(self.store.unacknowledged_count(), 0)
        self.assertTrue(self.store.recent()[0].acknowledged)


class SnapshotTests(StoreTestCase):
    def test_snapshot_is_written_and_linked(self):
        self.add(snapshot=b"\xff\xd8fake-jpeg")
        record = self.store.recent()[0]
        self.assertTrue(record.snapshot)
        self.assertTrue((self.store.snapshot_dir / record.snapshot).exists())

    def test_no_snapshot_means_no_file(self):
        self.add(snapshot=None)
        self.assertEqual(self.store.recent()[0].snapshot, "")
        self.assertEqual(list(self.store.snapshot_dir.glob("*.jpg")), [])

    def test_snapshots_can_be_disabled_entirely(self):
        store = EventStore(
            StorageConfig(save_snapshots=False, db_path="data/off.db"), root=self.root
        )
        store.record(camera_id="cam-01", event_type="x", severity="warning",
                     detail="", confidence=0.5, snapshot_bytes=b"jpeg")
        self.assertEqual(store.recent()[0].snapshot, "")


class RetentionTests(StoreTestCase):
    def test_expired_rows_and_files_are_purged(self):
        now = time.time()
        expired_id = self.add(at=now - 40 * 86400, snapshot=b"old")   # beyond 30 days
        kept_id = self.add(at=now - 1 * 86400, snapshot=b"new")       # inside the window
        by_id = {a.id: a for a in self.store.recent()}
        expired_file = self.store.snapshot_dir / by_id[expired_id].snapshot
        kept_file = self.store.snapshot_dir / by_id[kept_id].snapshot
        self.assertTrue(expired_file.exists() and kept_file.exists())

        removed = self.store.purge_expired(now=now)

        self.assertEqual(removed, 1)
        self.assertEqual([a.id for a in self.store.recent()], [kept_id])
        self.assertFalse(expired_file.exists(), "expired snapshot was not deleted")
        self.assertTrue(kept_file.exists(), "in-window snapshot must survive")

    def test_retention_can_be_switched_off(self):
        store = EventStore(
            StorageConfig(retention_days=0, db_path="data/keep.db"), root=self.root
        )
        store.record(camera_id="c", event_type="x", severity="warning",
                     detail="", confidence=0.1, at=time.time() - 9999 * 86400)
        self.assertEqual(store.purge_expired(), 0)
        self.assertEqual(len(store.recent()), 1)

    def test_purge_survives_an_already_deleted_snapshot(self):
        now = time.time()
        self.add(at=now - 60 * 86400, snapshot=b"gone")
        for path in self.store.snapshot_dir.glob("*.jpg"):
            path.unlink()
        self.assertEqual(self.store.purge_expired(now=now), 1)


if __name__ == "__main__":
    unittest.main()
