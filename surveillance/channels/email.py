"""Email alerts. Credentials come from the environment only."""

import logging
import smtplib
import time
from email.message import EmailMessage

log = logging.getLogger(__name__)


class EmailChannel:
    name = "email"

    def __init__(self, config, timeout=15):
        self.config = config
        self.timeout = timeout

    @property
    def enabled(self):
        return self.config.is_configured

    def build_message(self, alert, snapshot_bytes=None):
        message = EmailMessage()
        message["Subject"] = "[{}] {} on {}".format(
            alert.severity.upper(),
            alert.event_type.replace("_", " "),
            alert.camera_name,
        )
        message["From"] = self.config.sender
        message["To"] = ", ".join(self.config.recipients)
        message.set_content(
            "Smart Surveillance System alert\n"
            "\n"
            "Event      : {event}\n"
            "Severity   : {severity}\n"
            "Camera     : {camera} ({camera_id})\n"
            "Time       : {when}\n"
            "Confidence : {confidence:.1%}\n"
            "Detail     : {detail}\n"
            "\n"
            "Alert #{record} is recorded in the event log.\n".format(
                event=alert.event_type,
                severity=alert.severity,
                camera=alert.camera_name,
                camera_id=alert.camera_id,
                when=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(alert.at)),
                confidence=alert.confidence,
                detail=alert.detail,
                record=alert.record_id,
            )
        )
        if snapshot_bytes:
            message.add_attachment(
                snapshot_bytes,
                maintype="image",
                subtype="jpeg",
                filename="alert-{}.jpg".format(alert.record_id or "snapshot"),
            )
        return message

    def send(self, alert, snapshot_bytes=None):
        if not self.enabled:
            log.debug("email channel not configured, skipping %s", alert.event_type)
            return False

        message = self.build_message(alert, snapshot_bytes)
        try:
            with smtplib.SMTP(
                self.config.host, self.config.port, timeout=self.timeout
            ) as server:
                if self.config.use_tls:
                    server.starttls()
                server.login(self.config.username, self.config.password)
                server.send_message(message)
        except Exception:
            log.exception("email alert failed for %s", alert.event_type)
            return False

        log.info("emailed %s to %d recipient(s)",
                 alert.event_type, len(self.config.recipients))
        return True
