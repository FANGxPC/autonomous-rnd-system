"""
MEMBER 2 — One-time Google Calendar OAuth setup.

Creates token.json in the project root so calendar_tool.py can call the Calendar API.

Prerequisites:
  - .env with GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET (OAuth client type: Desktop).
  - Google Cloud: Calendar API enabled; OAuth consent screen configured.

Run (once per machine / after revoking access):
  python auth_setup.py
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

from calendar_tool import SCOPES

TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")


def main() -> None:
    load_dotenv()

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET in .env",
            file=sys.stderr,
        )
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    print("Opening browser for Google sign-in…")
    creds = flow.run_local_server(port=0, prompt="consent")

    if not creds.refresh_token:
        print(
            "Warning: no refresh_token. If Calendar stops working after 1 hour, "
            "delete token.json and run again with prompt=consent.",
            file=sys.stderr,
        )

    payload = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
    }
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Saved OAuth token to {TOKEN_PATH}")
    print("You can run: python calendar_tool.py  or  python test_member2.py")


if __name__ == "__main__":
    main()
