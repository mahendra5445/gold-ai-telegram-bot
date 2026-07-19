
"""
Trading Session Filter (based on UTC time)
London  : 08:00 - 16:00 UTC
New York: 13:00 - 21:00 UTC
Asian   : 00:00 - 08:00 UTC
"""

from datetime import datetime


def get_current_session():
    hour = datetime.utcnow().hour

    london = 8 <= hour < 16
    new_york = 13 <= hour < 21
    asian = 0 <= hour < 8

    if london and new_york:
        return "London + New York Overlap", True
    if london:
        return "London", True
    if new_york:
        return "New York", True
    if asian:
        return "Asian", False

    return "Off-Hours", False
