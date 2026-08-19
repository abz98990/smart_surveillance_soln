"""Smart Surveillance System.

A local, multi-camera threat detection pipeline: YOLO11 detectors feed a
behavioural analytics layer, which feeds a debounced alert manager, which
writes to an event log and notifies operators. A Flask dashboard renders the
annotated streams and the log.
"""

__version__ = "1.0.0"
