from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


if __name__ == "__main__":
    now = datetime.now(ZoneInfo("America/New_York"))
    should_run = now.weekday() in {0, 3} and now.hour == 6
    print("true" if should_run else "false")
