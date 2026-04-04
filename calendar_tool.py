# calendar_tool.py
"""
MEMBER 2 - THE INTEGRATOR
Action 2: Google Calendar MCP Tool
Creates Deep Work blocks on the user's calendar
"""

import os
import json
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

SCOPES      = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")


def _get_calendar_service():
    """Loads token.json and returns an authenticated Calendar client."""
    if not os.path.exists("token.json"):
        raise FileNotFoundError(
            "token.json not found. Run auth_setup.py first to authenticate."
        )
    with open("token.json") as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=creds)


def create_calendar_block(
    task_title: str,
    date: str,
    start_hour: int = 14,
    duration_hours: int = 2,
    description: str = ""
) -> str:
    """
    Creates a Deep Work time block on Google Calendar.
    Use this BEFORE creating a Kanban card so the date is confirmed.

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
        service   = _get_calendar_service()
        start_dt  = datetime.fromisoformat(date).replace(
                        hour=start_hour, minute=0, second=0
                    )
        end_dt    = start_dt + timedelta(hours=duration_hours)

        event = {
            "summary":     f"🔒 Deep Work: {task_title}",
            "description": description or f"Focused session for: {task_title}",
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "colorId":  "9",   # blueberry — visually distinct
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": 10}],
            },
        }

        created = service.events().insert(
            calendarId=CALENDAR_ID, body=event
        ).execute()

        link   = created.get("htmlLink", "no-link")
        result = (
            f"✅ Calendar block created: '🔒 Deep Work: {task_title}'\n"
            f"   Date: {date} | {start_hour}:00 → {start_hour + duration_hours}:00 IST\n"
            f"   Link: {link}"
        )
        print(result)
        return result

    except Exception as e:
        error = f"❌ Calendar error: {str(e)}"
        print(error)
        return error


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
        service   = _get_calendar_service()
        day_start = datetime.fromisoformat(date).replace(
                        hour=work_start, minute=0, second=0
                    )
        day_end   = datetime.fromisoformat(date).replace(
                        hour=work_end, minute=0, second=0
                    )

        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=day_start.isoformat() + "+05:30",
            timeMax=day_end.isoformat()   + "+05:30",
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        # Build busy list
        busy = []
        for ev in events_result.get("items", []):
            s = ev["start"].get("dateTime") or ev["start"].get("date")
            e = ev["end"].get("dateTime")   or ev["end"].get("date")
            if "T" in s:
                busy.append((
                    datetime.fromisoformat(s.replace("Z", "+00:00")),
                    datetime.fromisoformat(e.replace("Z", "+00:00")),
                ))

        # Find gaps ≥ 2 hours
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

        print(output)
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