"""Desktop notification helper.

Archived prototype - superseded by the surveillance/ package. Kept for the
development history; run `python run.py` from the project root for the
actual system. Defects found in review have been corrected so nothing in
the repository is broken, but these scripts are not maintained.
"""

from plyer import notification

APP_NAME = "Smart Surveillance System"


def notif(title="Threat detected", message="Check the surveillance dashboard."):
    """Raise a desktop notification.

    The original slept for one second inside this call, which stalled the
    capture loop on every alerting frame. Rate limiting belongs to the caller;
    see surveillance/alerts.py, which debounces and dispatches on a worker
    thread instead.
    """
    notification.notify(title=title, message=message, app_name=APP_NAME, timeout=10)
