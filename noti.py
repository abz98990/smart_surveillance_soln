import time

from plyer.utils import platform
from plyer import notification

def notif():
    notification.notify(
        title='Here is the title',
        message='Here is the message',
        app_name='Here is the application name'
    )
    time.sleep(1)