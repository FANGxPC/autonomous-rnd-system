# notion_tool.py
"""
MEMBER 2 - THE INTEGRATOR
Notion: Kanban rows and/or per-run pages under a Runs hub.

- NOTION_RUNS_PARENT_PAGE_ID: each pipeline run creates a child page under that hub (your "Runs" page).
  By default tasks are appended as to-do blocks on that page (simple, no extra database).
  Set NOTION_RUN_USE_KANBAN_DB=1 to instead create a new Kanban database on that child page.
- Legacy: omit NOTION_RUNS_PARENT_PAGE_ID; use NOTION_DATABASE_ID only.

Template DB property names are auto-detected; override with NOTION_PROP_*.
Notion API 2025-09-03: set NOTION_DATA_SOURCE_ID if schema auto-detect fails.
"""

from __future__ import annotations

import json
import os
import re
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

_notion = Client(auth=os.environ["NOTION_TOKEN"])

# Notion rich_text content max ~2000; stay under for safety.
_NOTION_RICHTEXT_MAX = 1990


def _chunk_plain_text(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    while text:
        chunks.append(text[:_NOTION_RICHTEXT_MAX])
        text = text[_NOTION_RICHTEXT_MAX:].lstrip()
    return chunks


def _default_annotations(*, bold: bool = False) -> dict[str, Any]:
    """Notion expects a full annotations object on rich_text runs (esp. bold)."""
    return {
        "bold": bold,
        "italic": False,
        "strikethrough": False,
        "underline": False,
        "code": False,
        "color": "default",
    }


def _paragraph_block_objects(body: str) -> list[dict[str, Any]]:
    """Plain paragraphs (no ** parsing); prefer _paragraph_blocks_from_markdown for user text."""
    ann = _default_annotations()
    return [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": ck},
                        "annotations": ann,
                    }
                ],
            },
        }
        for ck in _chunk_plain_text(body)
    ]


# List markers: ASCII - * +, Unicode bullets, MD + lists.
# Lines starting **... fail (no \s+ after first *) so they are not treated as bullets.
_BULLET_LINE = re.compile(r"^\s*[\-\*\+•·▪▸]\s+(.+)$")
_NUMBERED_LINE = re.compile(r"^\s*\d+\.\s+(.+)$")
_NUMBERED_PAREN_LINE = re.compile(r"^\s*\d+\)\s+(.+)$")
_HEADING_LINE = re.compile(r"^\s*(#{1,3})\s+(.+?)\s*$")
_URL_IN_LINE = re.compile(r"https?://[^\s\)\]\>\"\'\,]+")


def _rich_text_from_string(text: str) -> list[dict[str, Any]]:
    """Inline **bold** → Notion rich_text segments (no visible asterisks)."""
    text = (text or "").strip()
    if not text:
        return [
            {
                "type": "text",
                "text": {"content": " "},
                "annotations": _default_annotations(),
            }
        ]
    parts = re.split(r"(\*\*.+?\*\*)", text)
    rich: list[dict[str, Any]] = []
    for p in parts:
        if not p:
            continue
        if len(p) >= 4 and p.startswith("**") and p.endswith("**"):
            frag = p[2:-2]
            for ck in _chunk_plain_text(frag):
                rich.append(
                    {
                        "type": "text",
                        "text": {"content": ck},
                        "annotations": _default_annotations(bold=True),
                    }
                )
        else:
            for ck in _chunk_plain_text(p):
                rich.append(
                    {
                        "type": "text",
                        "text": {"content": ck},
                        "annotations": _default_annotations(),
                    }
                )
    return rich or [
        {
            "type": "text",
            "text": {"content": " "},
            "annotations": _default_annotations(),
        }
    ]


def _paragraph_blocks_from_markdown(body: str) -> list[dict[str, Any]]:
    """One or more paragraph blocks; always parses **bold** (any length)."""
    body = (body or "").strip()
    if not body:
        return []
    out: list[dict[str, Any]] = []
    for chunk in re.split(r"\n{2,}", body):
        chunk = chunk.strip()
        if not chunk:
            continue
        out.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": _rich_text_from_string(chunk)},
            }
        )
    return out


def _normalize_description_markdown(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\ufeff", "")
    text = text.replace("＊", "*")
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_+#.-]*\s*\n?", "", t)
        t = re.sub(r"\n```\s*$", "", t)
    lines_out: list[str] = []
    for line in t.split("\n"):
        line = re.sub(r"^(\s*)[•·▪▸]\s*", r"\1* ", line)
        lines_out.append(line)
    return "\n".join(lines_out).strip()


def _description_to_block_dicts(description: str) -> list[dict[str, Any]]:
    """
    Turn agent markdown-ish text into Notion blocks: real bullets/numbers/headings;
    **bold** becomes rich_text (asterisks are not shown).
    """
    text = _normalize_description_markdown(description)
    if not text:
        return []
    lines = text.split("\n")
    blocks: list[dict[str, Any]] = []
    para_buf: list[str] = []

    def flush_para() -> None:
        nonlocal para_buf
        if not para_buf:
            return
        body = "\n".join(para_buf).strip()
        para_buf = []
        if not body:
            return
        blocks.extend(_paragraph_blocks_from_markdown(body))

    for line in lines:
        hm = _HEADING_LINE.match(line)
        nm = _NUMBERED_LINE.match(line)
        npm = _NUMBERED_PAREN_LINE.match(line)
        m = _BULLET_LINE.match(line)
        if hm:
            flush_para()
            level = len(hm.group(1))
            title = hm.group(2).strip()
            htype = "heading_1" if level == 1 else "heading_2" if level == 2 else "heading_3"
            blocks.append(
                {
                    "object": "block",
                    "type": htype,
                    htype: {
                        "rich_text": _rich_text_from_string(
                            title[:_NOTION_RICHTEXT_MAX]
                        ),
                    },
                }
            )
        elif npm:
            flush_para()
            content = npm.group(1).strip()
            if content:
                blocks.append(
                    {
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {
                            "rich_text": _rich_text_from_string(
                                content[:_NOTION_RICHTEXT_MAX]
                            ),
                        },
                    }
                )
        elif nm:
            flush_para()
            content = nm.group(1).strip()
            if content:
                blocks.append(
                    {
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {
                            "rich_text": _rich_text_from_string(
                                content[:_NOTION_RICHTEXT_MAX]
                            ),
                        },
                    }
                )
        elif m:
            flush_para()
            content = m.group(1).strip()
            if content:
                blocks.append(
                    {
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": _rich_text_from_string(
                                content[:_NOTION_RICHTEXT_MAX]
                            ),
                        },
                    }
                )
        else:
            if not line.strip():
                flush_para()
            else:
                para_buf.append(line)
    flush_para()
    return blocks


def _sources_to_blocks(sources: str) -> list[dict[str, Any]]:
    """Heading + bulleted lines; URLs become clickable links."""
    src = (sources or "").strip()
    if not src:
        return []
    ann = _default_annotations()
    out: list[dict[str, Any]] = [
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "Sources & references"},
                        "annotations": ann,
                    }
                ],
            },
        },
    ]
    for raw_line in src.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        url_m = _URL_IN_LINE.search(line)
        if url_m:
            url = url_m.group(0).rstrip(".,);]")
            label = line.replace(url, "").strip(" -\u2022\t•")
            label = (label[:400] + "…") if len(label) > 420 else label
            if not label:
                label = url[:80] + ("…" if len(url) > 80 else "")
            rich = []
            if label:
                for ck in _chunk_plain_text(f"{label} "):
                    rich.append(
                        {
                            "type": "text",
                            "text": {"content": ck},
                            "annotations": ann,
                        }
                    )
            for ck in _chunk_plain_text(url):
                rich.append(
                    {
                        "type": "text",
                        "text": {"content": ck, "link": {"url": url}},
                        "annotations": ann,
                    }
                )
            out.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": rich},
                }
            )
        else:
            out.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": _rich_text_from_string(
                            line[:_NOTION_RICHTEXT_MAX]
                        ),
                    },
                }
            )
    return out


def _append_blocks_batched(parent_block_id: str, blocks: list[dict[str, Any]]) -> None:
    for i in range(0, len(blocks), 100):
        _notion.blocks.children.append(
            block_id=parent_block_id,
            children=blocks[i : i + 100],
        )


# New DB per pipeline run uses this fixed schema (matches Scrum agent: To Do / In Progress / Done).
FIXED_RUN_SCHEMA: dict[str, Any] = {
    "title_name": "Name",
    "status_name": "Status",
    "status_api_kind": "select",
    "date_name": "Deadline",
}


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


@dataclass(frozen=True)
class NotionRunContext:
    run_page_id: str
    run_page_url: str
    kanban_database_id: str | None = None


_run_ctx: ContextVar[NotionRunContext | None] = ContextVar(
    "notion_run_ctx", default=None
)

# ADK often runs tools on a worker thread where ContextVar is empty. Mirror run state in
# process env for the duration of one HTTP request (see begin/end). Not concurrency-safe.
_ENV_REQ_ACTIVE = "_RND_NOTION_REQ_ACTIVE"
_ENV_REQ_PAGE_ID = "_RND_NOTION_REQ_PAGE_ID"
_ENV_REQ_PAGE_URL = "_RND_NOTION_REQ_PAGE_URL"
_ENV_REQ_KANBAN_DB = "_RND_NOTION_REQ_KANBAN_DB"
_ENV_REQ_KANBAN_SCHEMA = "_RND_NOTION_REQ_KANBAN_SCHEMA"
_REQUEST_ENV_KEYS = (
    _ENV_REQ_ACTIVE,
    _ENV_REQ_PAGE_ID,
    _ENV_REQ_PAGE_URL,
    _ENV_REQ_KANBAN_DB,
    _ENV_REQ_KANBAN_SCHEMA,
)


def _clear_request_env() -> None:
    for k in _REQUEST_ENV_KEYS:
        os.environ.pop(k, None)


def _install_request_env(
    ctx: NotionRunContext, kanban_schema_json: str | None
) -> None:
    _clear_request_env()
    os.environ[_ENV_REQ_ACTIVE] = "1"
    os.environ[_ENV_REQ_PAGE_ID] = ctx.run_page_id
    os.environ[_ENV_REQ_PAGE_URL] = ctx.run_page_url
    if ctx.kanban_database_id:
        os.environ[_ENV_REQ_KANBAN_DB] = ctx.kanban_database_id
        if kanban_schema_json:
            os.environ[_ENV_REQ_KANBAN_SCHEMA] = kanban_schema_json


def _effective_ctx() -> NotionRunContext | None:
    c = _run_ctx.get()
    if c is not None:
        return c
    if os.environ.get(_ENV_REQ_ACTIVE) != "1":
        return None
    db = os.environ.get(_ENV_REQ_KANBAN_DB, "").strip() or None
    return NotionRunContext(
        run_page_id=os.environ[_ENV_REQ_PAGE_ID],
        run_page_url=os.environ.get(_ENV_REQ_PAGE_URL, ""),
        kanban_database_id=db,
    )

# Optional .env overrides (exact names as they appear in Notion template DB)
_ENV_TITLE = os.getenv("NOTION_PROP_TITLE", "").strip()
_ENV_STATUS = os.getenv("NOTION_PROP_STATUS", "").strip()
_ENV_DATE = os.getenv("NOTION_PROP_DATE", "").strip()
_ENV_DATA_SOURCE = os.getenv("NOTION_DATA_SOURCE_ID", "").strip()

_schema_cache: dict[str, dict[str, Any]] = {}


def _get_template_database_id() -> str:
    raw = os.getenv("NOTION_DATABASE_ID", "").strip()
    if not raw:
        raise ValueError(
            "Set NOTION_DATABASE_ID for standalone Notion tools, or use "
            "NOTION_RUNS_PARENT_PAGE_ID so each pipeline run gets its own page under Runs."
        )
    return _normalize_notion_id(raw)


def _current_database_id() -> str:
    ctx = _effective_ctx()
    if ctx is not None:
        if ctx.kanban_database_id:
            return ctx.kanban_database_id
        raise ValueError("Current run uses block mode; no Kanban database id.")
    return _get_template_database_id()


def _runs_use_kanban_db() -> bool:
    return os.getenv("NOTION_RUN_USE_KANBAN_DB", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _append_task_blocks_to_page(
    page_id: str,
    title: str,
    status: str,
    deadline: str,
    description: str,
    sources: str = "",
) -> None:
    header = f"{title}  [{status}]  due {deadline}"[:_NOTION_RICHTEXT_MAX]
    children: list[dict[str, Any]] = [
        {
            "object": "block",
            "type": "to_do",
            "to_do": {
                "rich_text": [{"type": "text", "text": {"content": header}}],
                "checked": False,
            },
        }
    ]
    if description.strip():
        children.append(
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Task details"}}
                    ],
                },
            }
        )
        children.extend(_description_to_block_dicts(description))
    if sources.strip():
        children.extend(_sources_to_blocks(sources))
    _append_blocks_batched(page_id, children)


def _plain_from_rich(rich: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for p in rich:
        if p.get("plain_text"):
            parts.append(str(p["plain_text"]))
        else:
            t = p.get("text") or {}
            parts.append(str(t.get("content", "")))
    return "".join(parts).strip()


def _list_tasks_from_run_page(page_id: str, status_filter: str) -> str:
    lines: list[str] = []
    cursor: str | None = None
    while True:
        kwargs: dict[str, Any] = {"block_id": page_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = _notion.blocks.children.list(**kwargs)
        for b in resp.get("results", []):
            if b.get("type") != "to_do":
                continue
            td = b.get("to_do") or {}
            text = _plain_from_rich(td.get("rich_text") or [])
            if not text:
                continue
            if status_filter and status_filter.lower() not in text.lower():
                continue
            lines.append(text)
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")

    if not lines:
        return (
            f"No to-do tasks found on this run page{' matching: ' + status_filter if status_filter else ''}."
        )
    out = f"📋 TASKS ON THIS RUN ({len(lines)}):\n" + "=" * 50 + "\n"
    out += "\n".join(f"• {ln}" for ln in lines)
    return out


def _fetch_property_schema(database_id: str) -> dict[str, Any]:
    """
    Notion-Version 2025-09-03: database retrieve often has no top-level `properties`;
    schema lives on child data sources. Older DBs still return `properties` on the database.
    """
    db = _notion.databases.retrieve(database_id=database_id)
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


def _build_schema_from_database(
    database_id: str, *, use_template_prop_overrides: bool
) -> dict[str, Any]:
    prop_schema = _fetch_property_schema(database_id)
    parsed = _parse_properties(prop_schema)
    if use_template_prop_overrides:
        title = _ENV_TITLE or parsed["title_name"]
        status_n = _ENV_STATUS or parsed["status_name"]
        date_n = _ENV_DATE or parsed["date_name"]
    else:
        title = parsed["title_name"]
        status_n = parsed["status_name"]
        date_n = parsed["date_name"]

    kind = parsed["status_api_kind"]
    if status_n:
        raw = prop_schema.get(status_n, {})
        t = raw.get("type")
        if t == "status":
            kind = "status"
        elif t == "select":
            kind = "select"

    return {
        "title_name": title,
        "status_name": status_n,
        "status_api_kind": kind,
        "date_name": date_n,
    }


def _get_schema() -> dict[str, Any]:
    ctx = _effective_ctx()
    if ctx is not None and ctx.kanban_database_id:
        raw = os.environ.get(_ENV_REQ_KANBAN_SCHEMA)
        if raw:
            return json.loads(raw)
        return FIXED_RUN_SCHEMA
    if ctx is not None and ctx.kanban_database_id is None:
        raise RuntimeError("_get_schema() invalid in Runs block mode")

    tid = _get_template_database_id()
    if tid in _schema_cache:
        return _schema_cache[tid]

    built = _build_schema_from_database(tid, use_template_prop_overrides=True)
    _schema_cache[tid] = built
    return built


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


def begin_notion_run_workspace(project_key: str) -> tuple[dict[str, str] | None, Token | None]:
    """
    If NOTION_RUNS_PARENT_PAGE_ID is set: create a child page under that hub.

    Default: tasks go on that page as to-do blocks (see guide). Optional NOTION_RUN_USE_KANBAN_DB=1
    adds a new Kanban database on the child page instead.

    Returns (meta, reset_token). Call end_notion_run_workspace(reset_token) when done.
    If the env var is unset, returns (None, None).
    """
    raw_parent = os.getenv("NOTION_RUNS_PARENT_PAGE_ID", "").strip()
    if not raw_parent:
        return None, None

    parent_id = _normalize_notion_id(raw_parent)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    safe_key = (project_key or "run").strip()[:180] or "run"
    page_title = f"{safe_key} — {stamp}"

    run_page = _notion.pages.create(
        parent={"page_id": parent_id},
        properties={
            "title": {
                "title": [{"type": "text", "text": {"content": page_title}}],
            }
        },
    )
    run_page_id = run_page["id"]
    run_url = run_page.get("url", "")

    db_id: str | None = None
    if _runs_use_kanban_db():
        db_title = f"Tasks — {safe_key}"[:2000]
        db = _notion.databases.create(
            parent={"type": "page_id", "page_id": run_page_id},
            title=[{"type": "text", "text": {"content": db_title}}],
            properties={
                "Name": {"title": {}},
                "Status": {
                    "select": {
                        "options": [
                            {"name": "To Do", "color": "gray"},
                            {"name": "In Progress", "color": "blue"},
                            {"name": "Done", "color": "green"},
                        ]
                    }
                },
                "Deadline": {"date": {}},
            },
        )
        db_id = _normalize_notion_id(db["id"])
    else:
        _notion.blocks.children.append(
            run_page_id,
            children=[
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [
                            {"type": "text", "text": {"content": "Tasks"}}
                        ],
                    },
                },
            ],
        )

    ctx = NotionRunContext(
        run_page_id=run_page_id,
        run_page_url=run_url,
        kanban_database_id=db_id,
    )
    reset_tok = _run_ctx.set(ctx)

    kanban_schema_json: str | None = None
    if db_id:
        try:
            sch = _build_schema_from_database(
                db_id, use_template_prop_overrides=False
            )
            kanban_schema_json = json.dumps(sch)
        except Exception:
            kanban_schema_json = json.dumps(FIXED_RUN_SCHEMA)
    _install_request_env(ctx, kanban_schema_json)

    meta: dict[str, str] = {
        "run_page_id": run_page_id,
        "run_page_url": run_url,
    }
    if db_id:
        meta["kanban_database_id"] = db_id
    return meta, reset_tok


def end_notion_run_workspace(reset_token: Token | None) -> None:
    _clear_request_env()
    if reset_token is not None:
        _run_ctx.reset(reset_token)


def create_kanban_card(
    title: str,
    status: str,
    deadline: str,
    description: str = "",
    sources: str = "",
) -> str:
    """
    Creates a task: either a Kanban row (template or per-run DB) or a to-do block on the run page.
    Use this to create project tasks with deadlines.

    Args:
        title:       The task title, e.g. 'ALU Design'
        status:      One of: 'To Do', 'In Progress', 'Done' (must match a Notion option)
        deadline:    ISO date string like '2026-05-15'
        description: Task detail: scope, bullets (* or - lines), **bold** labels, multiple paragraphs OK.
        sources:     Optional. Newline-separated URLs and citations; rendered under **Sources & references**
                     at the bottom of the card (clickable links when lines contain http/https URLs).

    Returns:
        A confirmation string with the Notion page URL
    """
    try:
        ctx = _effective_ctx()
        if ctx is not None and ctx.kanban_database_id is None:
            _append_task_blocks_to_page(
                ctx.run_page_id, title, status, deadline, description, sources
            )
            return (
                f"✅ Task added to run page: '{title}' [{status}] due {deadline} "
                f"→ {ctx.run_page_url}"
            )

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

        children: list[dict[str, Any]] = []
        if description.strip():
            children.append(
                {
                "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [
                            {"type": "text", "text": {"content": "Task details"}}
                        ],
                    },
                }
            )
            children.extend(_description_to_block_dicts(description))
        children.extend(_sources_to_blocks(sources))

        first_children = children[:100]
        create_kw: dict[str, Any] = {
            "parent": {"database_id": _current_database_id()},
            "properties": properties,
        }
        if first_children:
            create_kw["children"] = first_children
        page = _notion.pages.create(**create_kw)
        rest = children[100:]
        if rest:
            _append_blocks_batched(page["id"], rest)

        url = page.get("url", "no-url")
        return f"✅ Notion card created: '{title}' [{status}] due {deadline} → {url}"

    except Exception as e:
        return f"❌ Notion error: {str(e)}"


def list_kanban_cards(status_filter: str = "") -> str:
    """
    Lists tasks: Kanban rows (template or per-run DB) or to-do blocks on the run page.

    Args:
        status_filter: Optional status to filter by. Leave empty for all cards.

    Returns:
        A formatted string listing all matching cards.
    """
    try:
        ctx = _effective_ctx()
        if ctx is not None and ctx.kanban_database_id is None:
            return _list_tasks_from_run_page(ctx.run_page_id, status_filter)

        s = _get_schema()
        st_name = s["status_name"]
        st_kind = s["status_api_kind"]
        tname = s["title_name"]
        dname = s["date_name"]

        query_args: dict[str, Any] = {"database_id": _current_database_id()}

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


# ── Quick test (legacy template DB only) ───────────────────────────────────
if __name__ == "__main__":
    print("🧪 Testing Notion MCP Tool (template NOTION_DATABASE_ID)...\n")
    sch = _get_schema()
    print(
        f"Detected schema: title={sch['title_name']!r}, status={sch['status_name']!r} "
        f"({sch['status_api_kind']}), date={sch['date_name']!r}\n"
    )
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
    print(list_kanban_cards("To Do"))
    print("\n✅ Notion test complete!")
