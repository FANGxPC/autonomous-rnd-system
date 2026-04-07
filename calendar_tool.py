# calendar_tool.py
"""
MEMBER 2 - THE INTEGRATOR
Action 2: Google Calendar MCP Tool
Creates Deep Work blocks on the user's calendar
"""

import json
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")
IST = ZoneInfo("Asia/Kolkata")

# One Calendar API client per process (avoids rebuild + token read on every insert).
_calendar_service = None


def _spread_dates_inclusive(start: date, end: date, n: int) -> list[date]:
    """Evenly spaced calendar dates from start through end (inclusive); n >= 1."""
    if n < 1:
        return []
    if start > end:
        start, end = end, start
    span = (end - start).days
    if span <= 0:
        return [start] * n
    if n == 1:
        return [end]
    out: list[date] = []
    for i in range(n):
        off = int(round(i * span / (n - 1)))
        out.append(start + timedelta(days=min(off, span)))
    return out


def compute_spread_dates_for_plan(
    plan_end_date: str, num_tasks: int
) -> tuple[list[date] | None, str | None, bool]:
    """
    Shared date spacing: today (IST) through plan_end_date for num_tasks rows.
    Returns (dates, error_message, adjusted_past_deadline).
    """
    if num_tasks < 1 or num_tasks > 20:
        return None, "num_tasks must be between 1 and 20.", False
    raw = (plan_end_date or "").strip()[:32]
    try:
        end = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return (
            None,
            f"Invalid plan_end_date — use YYYY-MM-DD only. Got: {plan_end_date!r}",
            False,
        )

    today = datetime.now(IST).date()
    start = today
    adjusted = False
    if end < start:
        end = start + timedelta(days=14)
        adjusted = True

    dates = _spread_dates_inclusive(start, end, num_tasks)
    return dates, None, adjusted


def spread_task_dates(plan_end_date: str, num_tasks: int) -> str:
    """
    Suggests one ISO date per task, spread from today (Asia/Kolkata) through the plan end date.
    Then **create_calendar_block** per task (staggered hours) and **create_kanban_card** with matching deadlines.

    Args:
        plan_end_date: Target / milestone date, YYYY-MM-DD (from the user message deadline).
        num_tasks: Number of tasks you will schedule (1–20).

    Returns:
        Numbered list of ISO dates in chronological order for tasks 1..N.
    """
    dates, err, adjusted = compute_spread_dates_for_plan(plan_end_date, num_tasks)
    if err:
        return f"❌ {err}"
    assert dates is not None
    lines = [
        f"📆 **{num_tasks}** task dates ({dates[0]} → {dates[-1]}, Asia/Kolkata)."
    ]
    if adjusted:
        lines.append(
            "(Plan end was before today — using a 14-day forward window from today for spacing.)"
        )
    lines.append("Use **in order** for your tasks (earlier tasks → earlier dates):")
    for i, d in enumerate(dates, 1):
        lines.append(f"  {i}. {d.isoformat()}")
    lines.append(
        "For each row: **create_calendar_block** (`date` = that ISO day, `duration_hours=2`, **start_hour** "
        "by task index: 1→10, 2→14, 3→16, 4→11, 5→15, 6→9, 7→17, 8→13, then repeat). "
        "Then **create_kanban_card** with **deadline** = that same ISO date. Do not call get_free_slots first."
    )
    return "\n".join(lines)


def _get_calendar_service():
    """Loads token.json once per process and returns a cached Calendar client."""
    global _calendar_service
    if _calendar_service is not None:
        return _calendar_service

    token_path = "/secrets/token.json" if os.path.exists("/secrets/token.json") else "token.json"
    if not os.path.exists(token_path):
        raise FileNotFoundError(
            "token.json not found. Run auth_setup.py first to authenticate."
        )
    with open(token_path) as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    _calendar_service = build("calendar", "v3", credentials=creds)
    return _calendar_service


def _build_deep_work_event(
    task_title: str,
    day: date,
    start_hour: int,
    duration_hours: int,
    description: str,
) -> dict:
    base = datetime(day.year, day.month, day.day, tzinfo=IST)
    start_dt = base.replace(
        hour=start_hour, minute=0, second=0, microsecond=0
    )
    end_dt = start_dt + timedelta(hours=duration_hours)
    return {
        "summary": f"🔒 Deep Work: {task_title}",
        "description": description or f"Focused session for: {task_title}",
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": "Asia/Kolkata",
        },
        "colorId": "9",
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 10}],
        },
    }


def create_calendar_block(
    task_title: str,
    date: str,
    start_hour: int = 14,
    duration_hours: int = 2,
    description: str = ""
) -> str:
    """
    Creates a Deep Work time block on Google Calendar.
    Prefer calling this before the matching Kanban card; no need to query free slots first.

    Args:
        task_title:      Name of the task, e.g. 'ALU Design'
        date:            Date as ISO string, e.g. '2026-05-10'
        start_hour:      Start hour in 24h format (default 14 = 2 PM IST)
        duration_hours:  How many hours to block (default 2)
        description:     Optional notes for the calendar event

    Returns:
        Confirmation string with the Google Calendar event link
    """
    try:
        service = _get_calendar_service()
        day = datetime.strptime(date, "%Y-%m-%d").date()
        event = _build_deep_work_event(
            task_title, day, start_hour, duration_hours, description
        )

        created = service.events().insert(
            calendarId=CALENDAR_ID, body=event
        ).execute()

        raw_link = created.get("htmlLink") or "no-link"
        link = raw_link.strip() if isinstance(raw_link, str) else str(raw_link)
        # Single-line Link: avoids broken URLs when logs/UI concatenate lines (e.g. "\\n3").
        return (
            f"✅ Calendar block created: '🔒 Deep Work: {task_title}' | "
            f"Date: {date} {start_hour}:00–{start_hour + duration_hours}:00 IST | Link: {link}"
        )

    except Exception as e:
        return f"❌ Calendar error: {str(e)}"


def get_free_slots(date: str, work_start: int = 9, work_end: int = 20) -> str:
    """
    Finds 2-hour free slots on a given day by reading existing calendar events.
    Use this before scheduling to avoid conflicts.

    Args:
        date:        ISO date string like '2026-05-10'
        work_start:  Start of work window in 24h (default 9 AM)
        work_end:    End of work window in 24h (default 8 PM)

    Returns:
        A formatted string listing available 2-hour slots
    """
    try:
        service = _get_calendar_service()
        base = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=IST)
        day_start = base.replace(
            hour=work_start, minute=0, second=0, microsecond=0
        )
        day_end = base.replace(
            hour=work_end, minute=0, second=0, microsecond=0
        )

        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        busy: list[tuple[datetime, datetime]] = []
        for ev in events_result.get("items", []):
            s = ev["start"].get("dateTime") or ev["start"].get("date")
            e = ev["end"].get("dateTime") or ev["end"].get("date")
            if "T" not in str(s):
                continue
            b_start = datetime.fromisoformat(
                str(s).replace("Z", "+00:00")
            ).astimezone(IST)
            b_end = datetime.fromisoformat(
                str(e).replace("Z", "+00:00")
            ).astimezone(IST)
            busy.append((b_start, b_end))

        free_slots = []
        cursor = day_start
        for b_start, b_end in sorted(busy):
            gap_hours = (b_start - cursor).total_seconds() / 3600
            if gap_hours >= 2:
                free_slots.append((cursor, b_start))
            cursor = max(cursor, b_end)

        tail_hours = (day_end - cursor).total_seconds() / 3600
        if tail_hours >= 2:
            free_slots.append((cursor, day_end))

        if not free_slots:
            return f"📅 No 2-hour free slots found on {date}."

        output = f"📅 FREE SLOTS on {date}:\n"
        for s, e in free_slots:
            output += f"  • {s.strftime('%H:%M')} – {e.strftime('%H:%M')} IST\n"

        return output

    except Exception as e:
        return f"❌ Calendar read error: {str(e)}"


# ── Quick test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🧪 Testing Calendar MCP Tool...\n")

    TODAY = datetime.now().strftime("%Y-%m-%d")

    print("Checking free slots today:")
    print(get_free_slots(TODAY))

    print("\nCreating a test Deep Work block:")
    create_calendar_block(
        task_title="ALU Design",
        date=TODAY,
        start_hour=15,
        duration_hours=2,
        description="Implement 16-bit ALU in Verilog"
    )
    print("\n✅ Calendar test complete! Check your Google Calendar.")