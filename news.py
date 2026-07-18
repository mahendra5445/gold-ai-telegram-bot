from datetime import datetime, timedelta
import requests

NEWS_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def is_high_impact_news():
    try:
        response = requests.get(NEWS_URL, timeout=10)
        events = response.json()

        now = datetime.utcnow()

        for event in events:

            if event.get("impact") != "High":
                continue

            if event.get("currency") != "USD":
                continue

            date_str = event.get("date")

            if not date_str:
                continue

            event_time = datetime.fromisoformat(
                date_str.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            # News से 30 मिनट पहले और 30 मिनट बाद
            if abs((event_time - now).total_seconds()) <= 1800:
                return True

        return False

    except Exception as e:
        print(f"[NEWS ERROR] {e}")
        return False
