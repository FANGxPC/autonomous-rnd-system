"""
MEMBER 4 - BACKEND LEAD
File: main.py
FastAPI + ADK Runner: POST /trigger-pipeline runs the multi-agent graph and returns input + outcome JSON.
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import RedirectResponse
from google.adk.runners import InMemoryRunner
from google.genai import types
from notion_client.errors import APIResponseError
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from agents import ADK_LITE, ADK_MODEL, tech_lead_agent
from database import log_run_history
from mcp_bridge import mcp_http_asgi, mcp_http_lifespan
from notion_tool import begin_notion_run_workspace, end_notion_run_workspace

app = FastAPI(
    title="Deep-Tech Sprint - Autonomous R&D System",
    description="Google Gen AI APAC Hackathon — POST /trigger-pipeline to run the ADK agent pipeline.",
    version="1.0",
    lifespan=mcp_http_lifespan,
)

# Split dev (UI on :3000 etc.) + optional extra origins from CORS_ALLOW_ORIGINS (comma-separated)
_cors_origins = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
]
for _part in os.getenv("CORS_ALLOW_ORIGINS", "").split(","):
    _o = _part.strip()
    if _o and _o not in _cors_origins:
        _cors_origins.append(_o)

_cors_kw: dict[str, Any] = {
    "allow_origins": _cors_origins,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
_cors_rx = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "").strip()
if _cors_rx:
    _cors_kw["allow_origin_regex"] = _cors_rx
app.add_middleware(CORSMiddleware, **_cors_kw)

console = Console()


class TriggerRequest(BaseModel):
    prompt: str
    deadline: str = "2026-04-30"
    project_key: str = Field(default="hackathon_demo", description="Firestore + session scope")


def _user_message(req: TriggerRequest) -> str:
    base = (
        f"project_key: {req.project_key}\n"
        f"deadline: {req.deadline}\n\n"
        f"User request:\n{req.prompt}\n\n"
        "Use the memory tools with the given project_key. "
    )
    if ADK_LITE:
        return (
            base
            + "LITE / quota mode: avoid redundant tool calls (one memory pass when enough; don't repeat "
            "the same search). You still MUST transfer to scrum_master_agent for Notion Kanban cards "
            "and Google Calendar whenever the request is project work and a deadline is present. "
            "Transfer to research_agent only when citations or URLs are needed. "
            "After research_agent returns, your next step must be scrum_master_agent — not a solo summary."
        )
    return (
        base
        + "Save requirements and deadline to Firestore, retrieve any prior context, "
        "then coordinate research and planning via sub-agents. "
        "If you use research_agent, your next step after research returns must be scrum_master_agent "
        "(Notion + Calendar); do not end the run on research output alone."
    )


def _event_text(event: Any) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "".join(p.text for p in event.content.parts if getattr(p, "text", None)).strip()


def _is_vertex_or_gemini_quota_error(exc: BaseException) -> bool:
    s = str(exc).lower()
    return (
        "429" in str(exc)
        or "resource_exhausted" in s
        or "resource exhausted" in s
        or "too many requests" in s
    )


def _rate_limit_backoff_seconds(attempt_index: int, err_text: str) -> float:
    """Vertex often omits 'retry in Xs'; use escalating waits."""
    m = re.search(r"retry in ([\d.]+)\s*s", err_text, re.IGNORECASE)
    if m:
        return min(float(m.group(1)) + 3.0, 180.0)
    # attempt_index 0 after first failure, etc.
    base = 35.0 * (1.6 ** attempt_index)
    return min(base, 150.0)


def _extract_outcome(events: list[Any]) -> str:
    preferred = "tech_lead_agent"
    for ev in reversed(events):
        if getattr(ev, "author", None) != preferred:
            continue
        t = _event_text(ev)
        if t:
            return t
    for ev in reversed(events):
        if getattr(ev, "author", None) == "user":
            continue
        t = _event_text(ev)
        if t:
            return t
    return ""


def _pipeline_created_notion_cards(events: list[Any]) -> bool:
    """True if any model turn invoked create_kanban_card (Scrum → Notion)."""
    for event in events:
        content = getattr(event, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", None) or []:
            fc = getattr(part, "function_call", None)
            if fc is not None and getattr(fc, "name", "") == "create_kanban_card":
                return True
    return False


_CALENDAR_EVENT_URL_RE = re.compile(
    r"https://www\.google\.com/calendar/event\?[^\s\)\]\"']+",
    re.IGNORECASE,
)


def _strings_from_model_event(event: Any) -> list[str]:
    out: list[str] = []
    content = getattr(event, "content", None)
    if not content:
        return out
    for part in getattr(content, "parts", None) or []:
        if getattr(part, "text", None):
            out.append(part.text)
        fr = getattr(part, "function_response", None)
        if fr is not None:
            r = getattr(fr, "response", None)
            if r is not None:
                out.append(str(r))
    return out


def _extract_calendar_event_links(
    events: list[Any], outcome_text: str
) -> list[str]:
    """Collect Google Calendar event URLs from tool output and final summary."""
    seen: set[str] = set()
    ordered: list[str] = []
    for ev in events:
        for s in _strings_from_model_event(ev):
            for m in _CALENDAR_EVENT_URL_RE.finditer(s):
                u = m.group(0).rstrip(".,);]")
                if u not in seen:
                    seen.add(u)
                    ordered.append(u)
    for m in _CALENDAR_EVENT_URL_RE.finditer(outcome_text or ""):
        u = m.group(0).rstrip(".,);]")
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    return ordered


def _notion_hub_page_url() -> str | None:
    """Public URL for NOTION_RUNS_PARENT_PAGE_ID (Runs hub), if configured."""
    raw = os.getenv("NOTION_RUNS_PARENT_PAGE_ID", "").strip()
    if not raw:
        return None
    nid = re.sub(r"[^0-9a-fA-F]", "", raw)
    if len(nid) != 32:
        return None
    return f"https://www.notion.so/{nid}"


_NOTION_GUARD_MAX_NUDGES = 2


def _log_event(event: Any) -> None:
    author = getattr(event, "author", "?")
    styles = {
        "user": "bold blue",
        "tech_lead_agent": "bold magenta",
        "research_agent": "bold green",
        "scrum_master_agent": "bold yellow",
    }
    style = styles.get(author, "white")

    if not event.content or not event.content.parts:
        return

    printed_text = False
    for part in event.content.parts:
        if getattr(part, "text", None):
            console.print(f"[{style}][{author}][/] {part.text}", end="")
            printed_text = True
        elif getattr(part, "function_call", None):
            fc = part.function_call
            args = getattr(fc, "args", None) or {}
            console.print(
                f"[dim yellow]🔧 [{author}] tool → {fc.name}({args})[/dim yellow]"
            )
        elif getattr(part, "function_response", None):
            fr = part.function_response
            r = getattr(fr, "response", None)
            preview = str(r)[:200] + ("…" if r and len(str(r)) > 200 else "")
            console.print(f"[dim cyan]   ← result: {preview}[/dim cyan]")
    if printed_text:
        console.print()


async def _ensure_session(runner: InMemoryRunner, user_id: str, session_id: str) -> Any:
    session = await runner.session_service.get_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id,
    )
    if session:
        return session
    return await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id,
    )


@app.get("/health")
async def health():
    """Cloud Run / load balancer probe."""
    return {"status": "ok"}


@app.get("/api")
async def api_info():
    """JSON service info (UI is served at / when frontend/ is present)."""
    return {
        "service": "Deep-Tech Sprint API",
        "docs": "/docs",
        "pipeline": "POST /trigger-pipeline",
        "health": "/health",
        "env": {
            "ADK_LITE": "0 = default. 1 = leaner tool use; Scrum/Notion still required for project work with deadlines.",
            "ADK_MODEL": "default gemini-2.5-flash; set in .env if you hit 429 or change backend.",
        },
        "example_body": {
            "prompt": "Design a 16-bit RISC processor in Verilog with ALU",
            "deadline": "2026-04-30",
            "project_key": "verilog_alu_demo",
        },
    }


@app.post("/trigger-pipeline")
async def trigger_pipeline(request: TriggerRequest):
    """
    Runs the Tech Lead ADK agent (with sub-agents + Firestore tools).
    Returns echo of input and the model outcome summary.
    """
    user_id = "api_user"
    session_id = request.project_key
    started = datetime.now().isoformat()

    console.print(Rule("[bold cyan]PIPELINE START[/bold cyan]", style="cyan"))
    console.print(
        Panel.fit(
            f"[bold]Prompt[/bold]: {request.prompt}\n"
            f"[bold]Deadline[/bold]: {request.deadline}\n"
            f"[bold]Project key[/bold]: {request.project_key}",
            title="[bold]Input[/bold]",
            border_style="cyan",
        )
    )

    payload_in = {
        "prompt": request.prompt,
        "deadline": request.deadline,
        "project_key": request.project_key,
    }

    meta = {
        "model": ADK_MODEL,
        "adk_lite": ADK_LITE,
        "hint": "Ensure .env (Firebase, Vertex/API, Notion, Calendar) and token.json for Calendar. "
        "Set ADK_MODEL in .env if you hit 429.",
    }

    last_error: Exception | None = None
    max_attempts = 6

    notion_run: dict[str, str] | None = None
    notion_reset_token = None
    try:
        notion_run, notion_reset_token = begin_notion_run_workspace(
            request.project_key
        )
    except APIResponseError as e:
        console.print(Rule("[bold red]NOTION RUNS HUB[/bold red]", style="red"))
        console.print(f"[bold red]{e}[/bold red]")
        return JSONResponse(
            status_code=200,
            content={
                "status": "error",
                "input": payload_in,
                "outcome": None,
                "error": str(e),
                "notion_setup_hint": (
                    "Notion cannot access the page in NOTION_RUNS_PARENT_PAGE_ID. "
                    "In Notion, open that hub page (e.g. Testing hackathon) → Share → "
                    "invite your integration by name (e.g. autonomous-rnd-agent). "
                    "Confirm the id matches the page URL (32 hex chars, with or without hyphens)."
                ),
                "meta": meta,
                "started_at": started,
                "finished_at": datetime.now().isoformat(),
            },
        )

    if notion_run:
        meta = {**meta, "notion_run_page_url": notion_run["run_page_url"]}
        if notion_run.get("kanban_database_id"):
            meta["notion_kanban_database_id"] = notion_run["kanban_database_id"]
        console.print(
            f"[dim]Notion run workspace: {notion_run['run_page_url']}[/dim]"
        )

    try:
        for attempt in range(max_attempts):
            runner: InMemoryRunner | None = None
            try:
                runner = InMemoryRunner(
                    agent=tech_lead_agent,
                    app_name="deep_tech_sprint",
                )
                session = await _ensure_session(runner, user_id, session_id)
                message = _user_message(request)

                events: list[Any] = []
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session.id,
                    new_message=types.UserContent(parts=[types.Part(text=message)]),
                ):
                    events.append(event)
                    _log_event(event)

                guard_i = 0
                while (
                    notion_run
                    and not _pipeline_created_notion_cards(events)
                    and guard_i < _NOTION_GUARD_MAX_NUDGES
                ):
                    guard_i += 1
                    console.print(
                        "[yellow]Notion guard: no create_kanban_card yet — "
                        f"nudging Tech Lead ({guard_i}/{_NOTION_GUARD_MAX_NUDGES})[/yellow]"
                    )
                    nudge = (
                        "System reminder (pipeline guard): A Notion run workspace is active for this "
                        "request, but **create_kanban_card** was never called. You MUST "
                        "**transfer_to_agent** with agent_name **scrum_master_agent** now. "
                        "Scrum must call **create_kanban_card** at least twice (real tasks) using "
                        f"deadline **{request.deadline}** and the user’s project scope. "
                        "Do not reply with only documentation; update the board first, then summarize."
                    )
                    async for event in runner.run_async(
                        user_id=user_id,
                        session_id=session.id,
                        new_message=types.UserContent(
                            parts=[types.Part(text=nudge)]
                        ),
                    ):
                        events.append(event)
                        _log_event(event)

                outcome_text = _extract_outcome(events)
                finished = datetime.now().isoformat()

                console.print(Rule("[bold green]PIPELINE DONE[/bold green]", style="green"))

                summary_for_log = outcome_text[:500] if outcome_text else "completed (no text outcome)"
                try:
                    log_run_history(summary_for_log, request.prompt)
                except Exception:
                    pass

                cards_ok = _pipeline_created_notion_cards(events)
                meta_out = {
                    **meta,
                    **(
                        {
                            "notion_kanban_cards_created": cards_ok,
                            "notion_guard_nudges": guard_i,
                        }
                        if notion_run
                        else {}
                    ),
                }
                if notion_run and not cards_ok:
                    meta_out = {
                        **meta_out,
                        "notion_guard_warning": (
                            "Per-run Notion workspace was opened but no create_kanban_card ran "
                            f"after {guard_i} guard nudge(s). Check Scrum/Calendar tools and logs."
                        ),
                    }

                body = {
                    "status": "success",
                    "input": payload_in,
                    "outcome": {
                        "summary": outcome_text,
                        "event_count": len(events),
                    },
                    "meta": meta_out,
                    "started_at": started,
                    "finished_at": finished,
                }
                if notion_run:
                    body["notion"] = {
                        "run_page_url": notion_run["run_page_url"],
                        "run_page_id": notion_run["run_page_id"],
                        "kanban_cards_created": cards_ok,
                    }
                    if notion_run.get("kanban_database_id"):
                        body["notion"]["kanban_database_id"] = notion_run[
                            "kanban_database_id"
                        ]
                    _hub = _notion_hub_page_url()
                    if _hub:
                        body["notion"]["hub_page_url"] = _hub
                _cal = _extract_calendar_event_links(events, outcome_text)
                if _cal:
                    body["calendar_event_links"] = _cal
                await runner.close()
                return JSONResponse(content=body)

            except Exception as e:
                last_error = e
                if runner is not None:
                    await runner.close()
                    runner = None

                err_s = str(e)
                is_quota = _is_vertex_or_gemini_quota_error(e)
                if is_quota and attempt < max_attempts - 1:
                    delay = _rate_limit_backoff_seconds(attempt, err_s)
                    console.print(
                        f"[yellow]Quota/rate limit — sleeping {delay:.0f}s, "
                        f"retry {attempt + 2}/{max_attempts}[/yellow]"
                    )
                    await asyncio.sleep(delay)
                    continue

                console.print(Rule("[bold red]PIPELINE ERROR[/bold red]", style="red"))
                console.print(f"[bold red]{e}[/bold red]")
                err_body: dict[str, Any] = {
                    "status": "error",
                    "input": payload_in,
                    "outcome": None,
                    "error": str(last_error),
                    "meta": meta,
                    "started_at": started,
                    "finished_at": datetime.now().isoformat(),
                }
                if is_quota:
                    err_body["quota_hint"] = (
                        "Vertex/Gemini returned 429 RESOURCE_EXHAUSTED. Wait several minutes between runs; "
                        "set ADK_LITE=1 to ask the model to use fewer tools; try ADK_MODEL=gemini-2.0-flash-001 "
                        "or another Flash model in your region; confirm billing and Generative AI quota in GCP. "
                        "See https://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted"
                    )
                if notion_run:
                    err_body["notion"] = {
                        "run_page_url": notion_run["run_page_url"],
                        "run_page_id": notion_run["run_page_id"],
                    }
                    if notion_run.get("kanban_database_id"):
                        err_body["notion"]["kanban_database_id"] = notion_run[
                            "kanban_database_id"
                        ]
                    _hub_e = _notion_hub_page_url()
                    if _hub_e:
                        err_body["notion"]["hub_page_url"] = _hub_e
                return JSONResponse(status_code=200, content=err_body)
    finally:
        end_notion_run_workspace(notion_reset_token)


_FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
# Starlette Mount matches /mcp/{path}; bare /mcp must redirect to /mcp/
@app.api_route(
    "/mcp",
    methods=["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    include_in_schema=False,
)
async def _mcp_redirect_slash(request: Request) -> RedirectResponse:
    q = request.url.query
    return RedirectResponse(f"/mcp/{('?' + q) if q else ''}", status_code=307)


# MCP over HTTP (Streamable HTTP) — mount before catch-all static files
app.mount("/mcp", mcp_http_asgi)
if _FRONTEND_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(_FRONTEND_DIR), html=True),
        name="frontend",
    )


if __name__ == "__main__":
    _port = int(os.environ.get("PORT", "8000"))
    _host = os.environ.get("HOST", "0.0.0.0")
    _url = f"http://127.0.0.1:{_port}"
    console.print(f"[bold]Starting[/bold] [link={_url}]{_url}[/link]")
    console.print(f"Docs: [link={_url}/docs]{_url}/docs[/link]")
    if _FRONTEND_DIR.is_dir():
        console.print(f"UI: [link={_url}/]{_url}/[/link] (same origin as API)")
    console.print(
        f"MCP: [link={_url}/mcp/]{_url}/mcp/[/link] "
        f"({'Bearer + MCP_AUTH_TOKEN' if os.getenv('MCP_AUTH_TOKEN', '').strip() else 'no MCP_AUTH_TOKEN — open'})"
    )
    uvicorn.run(app, host=_host, port=_port)
