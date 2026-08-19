"""Alert delivery. Every channel exposes `name` and `send(alert)`."""

from surveillance.channels.desktop import DesktopChannel
from surveillance.channels.email import EmailChannel

__all__ = ["DesktopChannel", "EmailChannel", "build_channels"]


def build_channels(config):
    # Email is only registered when SMTP credentials are present, so an
    # unconfigured checkout runs on desktop alerts instead of logging a
    # failure per alert.
    channels = {"desktop": DesktopChannel()}
    email = EmailChannel(config.email)
    if email.enabled:
        channels["email"] = email
    return channels
