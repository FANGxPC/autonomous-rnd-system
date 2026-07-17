"""
MEMBER 2 — One-time Google Calendar OAuth setup.

Creates token.json in the project root so calendar_tool.py can call the Calendar API.

Prerequisites:
  - .env with GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET (OAuth client type: Desktop).
  - Google Cloud: Calendar API enabled; OAuth consent screen configured.

Run (once per machine / after revoking access):

  python auth_setup.py

**Cloud Workstations / SSH / remote IDE:** OAuth uses ``localhost:<random port>`` as the
redirect. The browser that completes sign-in must talk to the **same** machine that runs
this script — embedded “preview” panes often break with “Couldn't connect … port 80”.
Run ``python auth_setup.py`` on your **local laptop** (copy ``.env``), finish Google sign-in
in normal Chrome, then upload ``token.json`` to Secret Manager for Cloud Run.

Optional:

  python auth_setup.py --no-browser          # print URL; open it on the same machine
  python auth_setup.py --bind-all            # listen on 0.0.0.0 for Docker / port-forward

If the API later returns ``invalid_grant`` / failed token refresh: your saved
``token.json`` no longer matches Google (revoked app, wrong OAuth client
credentials in ``.env``, or changed Google password). Delete ``token.json``,
check ``GOOGLE_CLIENT_ID`` / ``GOOGLE_CLIENT_SECRET`` match a **Desktop** OAuth
client in Google Cloud, then run this script again.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

from calendar_tool import SCOPES

TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Calendar OAuth — writes token.json")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Print the auth URL instead of opening a browser (still uses localhost callback).",
    )
    parser.add_argument(
        "--bind-all",
        action="store_true",
        help="Bind redirect server to 0.0.0.0 (useful inside Docker or with SSH port forwarding).",
    )
    args = parser.parse_args()

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
    if args.no_browser:
        print("Open this URL in a browser **on the same machine** as this script:")
    else:
        print("Opening browser for Google sign-in…")

    server_kwargs: dict = {
        "port": 0,
        "prompt": "consent",
        "open_browser": not args.no_browser,
    }
    if args.bind_all:
        server_kwargs["bind_addr"] = "0.0.0.0"

    creds = flow.run_local_server(**server_kwargs)

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

