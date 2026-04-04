# notion_tool.py
"""
MEMBER 2 - THE INTEGRATOR
Action 1: Notion MCP Tool
Replaces mock_create_ticket in scrum_master_agent

Property names are auto-detected from your Notion database schema (title / status|select / date).
Override with NOTION_PROP_* in .env if needed.
Notion API 2025-09-03: set NOTION_DATA_SOURCE_ID if schema auto-detect fails (optional).
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

_notion = Client(auth=os.environ["NOTION_TOKEN"])


def _normalize_notion_id(raw: str) -> str:
    """UUIDs in URLs are often 32 hex chars without hyphens; Notion API accepts hyphenated form."""
    s = raw.strip()
    if (
        len(s) == 32
        and "-" not in s
        and all(c in "0123456789abcdefABCDEF" for c in s)
    ):
        return f"{s[0:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:32]}"
    return s


_DB_ID = _normalize_notion_id(os.environ["NOTION_DATABASE_ID"])

# Optional .env overrides (exact names as they appear in Notion)
_ENV_TITLE = os.getenv("NOTION_PROP_TITLE", "").strip()
_ENV_STATUS = os.getenv("NOTION_PROP_STATUS", "").strip()
_ENV_DATE = os.getenv("NOTION_PROP_DATE", "").strip()
_ENV_DATA_SOURCE = os.getenv("NOTION_DATA_SOURCE_ID", "").strip()

_schema_cache: dict[str, Any] | None = None


def _fetch_property_schema() -> dict[str, Any]:
    """
    Notion-Version 2025-09-03: database retrieve often has no top-level `properties`;
    schema lives on child data sources. Older DBs still return `properties` on the database.
    """
    db = _notion.databases.retrieve(database_id=_DB_ID)
    props = db.get("properties")
    if isinstance(props, dict) and props:
        return props

    ds_id_raw = _ENV_DATA_SOURCE or ""
    if not ds_id_raw:
        sources = db.get("data_sources") or []
        if not sources:
            raise ValueError(
                "Notion database has no 'properties' and no 'data_sources'. "
                f"Keys returned: {list(db.keys())}. "
                "Use the database id from the URL or set NOTION_DATA_SOURCE_ID in .env."
            )
        first = sources[0]
        ds_id_raw = first.get("id") if isinstance(first, dict) else str(first)

    ds_id = _normalize_notion_id(ds_id_raw)
    ds = _notion.data_sources.retrieve(data_source_id=ds_id)
    sp = ds.get("properties")
    if not isinstance(sp, dict) or not sp:
        raise ValueError(
            f"Data source {ds_id!r} has no 'properties'. Keys: {list(ds.keys())}"
        )
    return sp


def _parse_properties(meta: dict[str, Any]) -> dict[str, Any]:
    """Map DB columns to keys we need: title_name, status_name, status_api_kind, date_name."""
    title_name = None
    status_name = None
    status_api_kind = None  # "status" | "select"
    date_name = None
    date_name_preferred = None

    for pname, pdef in meta.items():
        ptype = pdef.get("type")
        if ptype == "title":
            title_name = pname
        elif ptype == "status":
            status_name = pname
            status_api_kind = "status"
        elif ptype == "select" and status_name is None:
            # Kanban boards often use select before status type existed
            low = pname.lower()
            if "status" in low or "state" in low or "stage" in low:
                status_name = pname
                status_api_kind = "select"
        elif ptype == "date":
            low = pname.lower()
            if any(k in low for k in ("deadline", "due", "date")):
                date_name_preferred = pname
            if date_name is None:
                date_name = pname

    if date_name_preferred:
        date_name = date_name_preferred

    # Fallback: any remaining select as status if we never found status
    if status_name is None:
        for pname, pdef in meta.items():
            if pdef.get("type") == "select":
                status_name = pname
                status_api_kind = "select"
                break

    return {
        "title_name": title_name,
        "status_name": status_name,
        "status_api_kind": status_api_kind,
        "date_name": date_name,
    }


def _get_schema() -> dict[str, Any]:
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    prop_schema = _fetch_property_schema()
    parsed = _parse_properties(prop_schema)

    title = _ENV_TITLE or parsed["title_name"]
    status_n = _ENV_STATUS or parsed["status_name"]
    date_n = _ENV_DATE or parsed["date_name"]

    kind = parsed["status_api_kind"]
    if status_n and _ENV_STATUS:
        raw = prop_schema.get(status_n, {})
        t = raw.get("type")
        if t == "status":
            kind = "status"
        elif t == "select":
            kind = "select"

    _schema_cache = {
        "title_name": title,
        "status_name": status_n,
        "status_api_kind": kind,
        "date_name": date_n,
    }
    return _schema_cache


def _rich_title(prop: dict[str, Any]) -> str:
    parts = prop.get("title") or []
    if not parts:
        return "Untitled"
    return parts[0].get("plain_text") or parts[0].get("text", {}).get("content", "Untitled")


def _rich_status(prop: dict[str, Any], kind: str) -> str:
    if kind == "status":
        st = prop.get("status")
        return st["name"] if st else "No status"
    st = prop.get("select")
    return st["name"] if st else "No status"


def _rich_date(prop: dict[str, Any]) -> str:
    d = prop.get("date")
    return d["start"] if d else "No deadline"


def create_kanban_card(title: str, status: str, deadline: str, description: str = "") -> str:
    """
    Creates a real Kanban card in the Notion database.
    Use this to create project tasks with deadlines.

    Args:
        title:       The task title, e.g. 'ALU Design'
        status:      One of: 'To Do', 'In Progress', 'Done' (must match a Notion option)
        deadline:    ISO date string like '2026-05-15'
        description: Optional extra detail about the task

    Returns:
        A confirmation string with the Notion page URL
    """
    try:
        s = _get_schema()
        tname, st_name, st_kind, dname = (
            s["title_name"],
            s["status_name"],
            s["status_api_kind"],
            s["date_name"],
        )
        if not tname:
            return "❌ Notion error: No title column found. Add a title property or set NOTION_PROP_TITLE in .env."

        properties: dict[str, Any] = {
            tname: {"title": [{"text": {"content": title}}]},
        }
        if st_name:
            if st_kind == "status":
                properties[st_name] = {"status": {"name": status}}
            elif st_kind == "select":
                properties[st_name] = {"select": {"name": status}}

        if deadline and dname:
            properties[dname] = {"date": {"start": deadline}}

        children = []
        if description:
            children.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"type": "text", "text": {"content": description}}
                        ]
                    },
                }
            )

        page = _notion.pages.create(
            parent={"database_id": _DB_ID},
            properties=properties,
            children=children,
        )

        url = page.get("url", "no-url")
        return f"✅ Notion card created: '{title}' [{status}] due {deadline} → {url}"

    except Exception as e:
        return f"❌ Notion error: {str(e)}"


def list_kanban_cards(status_filter: str = "") -> str:
    """
    Lists existing Kanban cards from Notion.
    Optionally filter by status: 'To Do', 'In Progress', or 'Done'.

    Args:
        status_filter: Optional status to filter by. Leave empty for all cards.

    Returns:
        A formatted string listing all matching cards.
    """
    try:
        s = _get_schema()
        st_name = s["status_name"]
        st_kind = s["status_api_kind"]
        tname = s["title_name"]
        dname = s["date_name"]

        query_args: dict[str, Any] = {"database_id": _DB_ID}

        if status_filter and st_name:
            if st_kind == "status":
                query_args["filter"] = {
                    "property": st_name,
                    "status": {"equals": status_filter},
                }
            else:
                query_args["filter"] = {
                    "property": st_name,
                    "select": {"equals": status_filter},
                }

        results = _notion.databases.query(**query_args).get("results", [])

        if not results:
            return f"No cards found{' with status: ' + status_filter if status_filter else ''}."

        output = f"📋 NOTION KANBAN CARDS ({len(results)} found):\n" + "=" * 50 + "\n"

        for page in results:
            props = page["properties"]
            tit = _rich_title(props.get(tname, {})) if tname else "Untitled"
            stat = (
                _rich_status(props.get(st_name, {}), st_kind)
                if st_name
                else "—"
            )
            due = _rich_date(props.get(dname, {})) if dname else "—"
            output += f"• {tit} | {stat} | Due: {due}\n"

        return output

    except Exception as e:
        return f"❌ Notion list error: {str(e)}"


# ── Quick test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🧪 Testing Notion MCP Tool...\n")
    sch = _get_schema()
    print(f"Detected schema: title={sch['title_name']!r}, status={sch['status_name']!r} ({sch['status_api_kind']}), date={sch['date_name']!r}\n")
    create_kanban_card(
        title="ALU Design",
        status="To Do",
        deadline="2026-05-10",
        description="Implement 16-bit ALU with ADD, SUB, AND, OR, XOR",
    )
    create_kanban_card(
        title="Register File",
        status="To Do",
        deadline="2026-05-15",
        description="16 general-purpose registers, dual read port",
    )
    print("\nListing all To Do cards:")
    list_kanban_cards("To Do")
    print("\n✅ Notion test complete!")
