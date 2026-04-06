"""
MCP (Model Context Protocol) HTTP surface for the same tools the ADK agents use.

Mounted at **`/mcp/`** on the FastAPI app (bare **`/mcp`** redirects with **307**). When MCP_AUTH_TOKEN is set, require either:
  Authorization: Bearer <token>
  X-MCP-API-Key: <token>

See README and DEPLOY.md for testing.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from fastmcp import FastMCP

from calendar_tool import create_calendar_block, get_free_slots
from database import retrieve_context_tool, save_project_context_tool
from notion_tool import create_kanban_card, list_kanban_cards
from research_tool import search_arxiv, search_web_snippets


def _build_mcp() -> FastMCP:
    mcp = FastMCP(
        "Deep-Tech Sprint — R&D tools",
        instructions=(
            "Tools for research (web, arXiv), Firestore memory, Notion Kanban, "
            "and Google Calendar Deep Work blocks. Matches the ADK agent tool layer."
        ),
    )

    @mcp.tool
    def mcp_search_web_snippets(query: str, max_results: int = 8) -> str:
        """Search the web via ddgs; returns titles, URLs, and snippets."""
        return search_web_snippets(query, max_results)

    @mcp.tool
    def mcp_search_arxiv(query: str, max_results: int = 5) -> str:
        """Search arXiv for papers."""
        return search_arxiv(query, max_results)

    @mcp.tool
    def mcp_save_project_context(
        project_key: str,
        category: str,
        value: str,
        notes: str = "",
    ) -> str:
        """Save structured context to Firestore for a project."""
        return save_project_context_tool(project_key, category, value, notes)

    @mcp.tool
    def mcp_retrieve_project_context(project_key: str, category: str = "") -> str:
        """Retrieve Firestore memory for a project (empty category = all)."""
        return retrieve_context_tool(project_key, category or None)

    @mcp.tool
    def mcp_create_kanban_card(
        title: str,
        status: str,
        deadline: str,
        description: str = "",
        sources: str = "",
    ) -> str:
        """Create a Notion Kanban card or run-page task (uses active Notion context / template DB)."""
        return create_kanban_card(title, status, deadline, description, sources)

    @mcp.tool
    def mcp_list_kanban_cards(status_filter: str = "") -> str:
        """List Notion Kanban cards or run-page todos."""
        return list_kanban_cards(status_filter)

    @mcp.tool
    def mcp_get_free_slots(date: str, work_start: int = 9, work_end: int = 20) -> str:
        """Find free 2-hour slots on a given ISO date (uses Google Calendar)."""
        return get_free_slots(date, work_start, work_end)

    @mcp.tool
    def mcp_create_calendar_block(
        task_title: str,
        date: str,
        start_hour: int = 14,
        duration_hours: int = 2,
        description: str = "",
    ) -> str:
        """Create a Deep Work block on Google Calendar (OAuth token.json on server)."""
        return create_calendar_block(
            task_title, date, start_hour, duration_hours, description
        )

    return mcp


_mcp = _build_mcp()
_raw_mcp_http_app = _mcp.http_app(path="/")


class MCPAuthASGIWrapper:
    """Optional shared-secret gate in front of the FastMCP ASGI app."""

    __slots__ = ("_app", "_secret")

    def __init__(self, app: Any, secret: str) -> None:
        self._app = app
        self._secret = secret

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        raw_headers = scope.get("headers") or []
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in raw_headers}
        auth = headers.get("authorization", "")
        key = headers.get("x-mcp-api-key", "")
        bearer_ok = auth.startswith("Bearer ") and auth[7:] == self._secret
        key_ok = key == self._secret
        if not (bearer_ok or key_ok):
            body = b'{"detail":"Invalid or missing MCP authentication. Use Authorization: Bearer <MCP_AUTH_TOKEN> or X-MCP-API-Key."}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"content-length", str(len(body)).encode("ascii")],
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self._app(scope, receive, send)


_secret = os.getenv("MCP_AUTH_TOKEN", "").strip()
mcp_http_asgi: Any = (
    MCPAuthASGIWrapper(_raw_mcp_http_app, _secret) if _secret else _raw_mcp_http_app
)
mcp_http_lifespan = _raw_mcp_http_app.lifespan
