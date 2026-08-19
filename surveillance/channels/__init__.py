"""Alert delivery channels.

Every channel exposes ``name`` and ``send(alert)``. Channels are constructed
once at startup and called from the alert dispatch thread.
"""

from surveillance.channels.desktop import DesktopChannel
from surveillance.channels.email import EmailChannel

__all__ = ["DesktopChannel", "EmailChannel", "build_channels"]


def build_channels(config):
    """Return the channel registry the AlertManager dispatches through.

    The email channel is only registered when SMTP credentials are present in
    the environment, so an unconfigured checkout runs on desktop alerts alone
    instead of logging a failure per alert.
    """
    channels = {"desktop": DesktopChannel()}
    email = EmailChannel(config.email)
    if email.enabled:
        channels["email"] = email
    return channels
