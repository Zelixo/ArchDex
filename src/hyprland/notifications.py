import notify2
import os

APP_NAME = "Pokedex aarch64"

def init_notifications():
    if not notify2.is_initted():
        notify2.init(APP_NAME)

def send_notification(summary, message, icon="dialog-information", timeout=notify2.EXPIRES_DEFAULT):
    init_notifications()
    try:
        n = notify2.Notification(summary, message, icon)
        n.set_timeout(timeout)
        n.show()
    except Exception as e:
        print(f"Error sending notification: {e}")

