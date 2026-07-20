from datetime import datetime, timedelta, timezone
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
            )

            # BUG FIX: the feed's timestamps carry a real UTC offset (not
            # always Z/UTC) - naively stripping tzinfo without converting
            # first compared local wall-clock time against UTC "now",
            # which was off by several hours for any non-UTC event and
            # could make the news filter fire at the wrong time (or miss
            # the window entirely).
            if event_time.tzinfo is not None:
                event_time = event_time.astimezone(timezone.utc).replace(tzinfo=None)

            # News से 30 मिनट पहले और 30 मिनट बाद
            if abs((event_time - now).total_seconds()) <= 1800:
                return True

        return False

    except Exception as e:
        print(f"[NEWS ERROR] {e}")
        return False
