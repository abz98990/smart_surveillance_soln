"""Desktop notification channel.

Called from the alert dispatch thread, never from a camera loop, so it is free
to take as long as the platform needs. It contains no sleep of its own.
"""

import logging

log = logging.getLogger(__name__)

APP_NAME = "Smart Surveillance System"


class DesktopChannel:
    name = "desktop"

    def __init__(self, timeout=10):
        self.timeout = timeout
        self._notification = None

    def _backend(self):
        if self._notification is None:
            from plyer import notification  # noqa: PLC0415 - optional dependency

            self._notification = notification
        return self._notification

    def send(self, alert):
        try:
            self._backend().notify(
                title=alert.title,
                message=alert.message,
                app_name=APP_NAME,
                timeout=self.timeout,
            )
        except Exception:
            # A missing notification daemon must never stop the pipeline.
            log.exception("desktop notification failed")
            return False
        return True
