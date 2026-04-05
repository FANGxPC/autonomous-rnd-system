"""
MEMBER 4 - BACKEND LEAD
File: main.py
FastAPI + ADK Runner: POST /trigger-pipeline runs the multi-agent graph and returns input + outcome JSON.
"""

import asyncio
import re
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

load_dotenv()

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from google.adk.runners import InMemoryRunner
from google.genai import types
from notion_client.errors import APIResponseError
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from agents import ADK_LITE, ADK_MODEL, tech_lead_agent
from database import log_run_history
from notion_tool import begin_notion_run_workspace, end_notion_run_workspace

app = FastAPI(
    title="Deep-Tech Sprint - Autonomous R&D System",
    description="Google Gen AI APAC Hackathon — POST /trigger-pipeline to run the ADK agent pipeline.",
    version="1.0",
)

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
            + "Follow LITE instructions: you have all tools yourself — no sub-agent transfers. "
            "Minimize tool calls to avoid API rate limits."
        )
    return (
        base
        + "Save requirements and deadline to Firestore, retrieve any prior context, "
        "then coordinate research and planning via sub-agents."
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


@app.get("/")
async def root():
    return {
        "service": "Deep-Tech Sprint API",
        "docs": "/docs",
        "pipeline": "POST /trigger-pipeline",
        "env": {
            "ADK_LITE": "0 (default) = full Tech Lead + Research + Scrum. 1 = shorter prompt only (graph still full).",
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

                outcome_text = _extract_outcome(events)
                finished = datetime.now().isoformat()

                console.print(Rule("[bold green]PIPELINE DONE[/bold green]", style="green"))

                summary_for_log = outcome_text[:500] if outcome_text else "completed (no text outcome)"
                try:
                    log_run_history(summary_for_log, request.prompt)
                except Exception:
                    pass

                body = {
                    "status": "success",
                    "input": payload_in,
                    "outcome": {
                        "summary": outcome_text,
                        "event_count": len(events),
                    },
                    "meta": meta,
                    "started_at": started,
                    "finished_at": finished,
                }
                if notion_run:
                    body["notion"] = {
                        "run_page_url": notion_run["run_page_url"],
                        "run_page_id": notion_run["run_page_id"],
                    }
                    if notion_run.get("kanban_database_id"):
                        body["notion"]["kanban_database_id"] = notion_run[
                            "kanban_database_id"
                        ]
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
                return JSONResponse(status_code=200, content=err_body)
    finally:
        end_notion_run_workspace(notion_reset_token)


if __name__ == "__main__":
    console.print("[bold]Starting[/bold] [link=http://localhost:8000]http://localhost:8000[/link]")
    console.print("Docs: [link=http://localhost:8000/docs]http://localhost:8000/docs[/link]")
    uvicorn.run(app, host="0.0.0.0", port=8000)
