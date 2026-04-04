# notion_tool.py
"""
MEMBER 2 - THE INTEGRATOR
Action 1: Notion MCP Tool
Replaces mock_create_ticket in scrum_master_agent
"""

import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

_notion = Client(auth=os.environ["NOTION_TOKEN"])
_DB_ID  = os.environ["NOTION_DATABASE_ID"]


def create_kanban_card(title: str, status: str, deadline: str, description: str = "") -> str:
    """
    Creates a real Kanban card in the Notion database.
    Use this to create project tasks with deadlines.

    Args:
        title:       The task title, e.g. 'ALU Design'
        status:      One of: 'To Do', 'In Progress', 'Done'
        deadline:    ISO date string like '2026-05-15'
        description: Optional extra detail about the task

    Returns:
        A confirmation string with the Notion page URL
    """
    try:
        properties = {
            "Name": {
                "title": [{"text": {"content": title}}]
            },
            "Status": {
                "select": {"name": status}
            },
        }

        if deadline:
            properties["Deadline"] = {"date": {"start": deadline}}

        children = []
        if description:
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": description}}]
                }
            })

        page = _notion.pages.create(
            parent={"database_id": _DB_ID},
            properties=properties,
            children=children,
        )

        url = page.get("url", "no-url")
        result = f"✅ Notion card created: '{title}' [{status}] due {deadline} → {url}"
        print(result)
        return result

    except Exception as e:
        error = f"❌ Notion error: {str(e)}"
        print(error)
        return error


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
        query_args = {"database_id": _DB_ID}

        if status_filter:
            query_args["filter"] = {
                "property": "Status",
                "select": {"equals": status_filter}
            }

        results = _notion.databases.query(**query_args).get("results", [])

        if not results:
            return f"No cards found{' with status: ' + status_filter if status_filter else ''}."

        output = f"📋 NOTION KANBAN CARDS ({len(results)} found):\n" + "=" * 50 + "\n"

        for page in results:
            props = page["properties"]

            title_list = props.get("Name", {}).get("title", [])
            title = title_list[0]["text"]["content"] if title_list else "Untitled"

            status_obj = props.get("Status", {}).get("select")
            status = status_obj["name"] if status_obj else "No status"

            date_obj = props.get("Deadline", {}).get("date")
            deadline = date_obj["start"] if date_obj else "No deadline"

            output += f"• {title} | {status} | Due: {deadline}\n"

        print(output)
        return output

    except Exception as e:
        return f"❌ Notion list error: {str(e)}"


# ── Quick test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🧪 Testing Notion MCP Tool...\n")
    create_kanban_card(
        title="ALU Design",
        status="To Do",
        deadline="2026-05-10",
        description="Implement 16-bit ALU with ADD, SUB, AND, OR, XOR"
    )
    create_kanban_card(
        title="Register File",
        status="To Do",
        deadline="2026-05-15",
        description="16 general-purpose registers, dual read port"
    )
    print("\nListing all To Do cards:")
    list_kanban_cards("To Do")
    print("\n✅ Notion test complete!")