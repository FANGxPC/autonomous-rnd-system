"""
ADK agents: Tech Lead (Firestore) + Research (web + optional arXiv) + Scrum (Notion + Calendar) + Workspace Prep.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent

from calendar_tool import create_calendar_block, get_free_slots
from database import memory_tools_phase3
from notion_tool import create_kanban_card, list_kanban_cards
from research_tool import search_arxiv, search_web_snippets
from workspace_tool import prepare_project_workspace

load_dotenv()

ADK_MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")
ADK_LITE = True


# ----------------------------
# Research Agent
# ----------------------------

research_agent = Agent(
    name="research_agent",
    model=ADK_MODEL,
    description="Finds sources via web search (DuckDuckGo); optional arXiv for papers.",
    instruction="""
You are the Research Agent (sub-agent only).

When given a technical topic:
1. Call search_web_snippets first with a short keyword query.
2. If academic preprints are needed, call search_arxiv.
3. Cite URLs from tool output.

Keep output concise bullet points only.
""",
    tools=[search_web_snippets, search_arxiv],
)


# ----------------------------
# Scrum Master Agent
# ----------------------------

scrum_master_agent = Agent(
    name="scrum_master_agent",
    model=ADK_MODEL,
    description="Creates real Kanban cards in Notion and blocks Deep Work time on Google Calendar.",
    instruction="""
You are the Scrum Master Agent.

When given a project and deadline, you MUST:

1. Call get_free_slots
2. Call create_calendar_block
3. Call create_kanban_card for EACH task

Always create calendar blocks BEFORE Notion cards.
Use status 'To Do'.
""",
    tools=[
        get_free_slots,
        create_calendar_block,
        create_kanban_card,
        list_kanban_cards,
    ],
)


# ----------------------------
# Workspace Prep Agent (REAL)
# ----------------------------

workspace_prep_agent = Agent(
    name="workspace_prep_agent",
    model=ADK_MODEL,
    description="Creates a real starter folder layout and README on disk.",
    instruction="""
You are the Workspace Preparation Agent.

After planning is clear:

1. Call prepare_project_workspace
2. Use a filesystem-safe project name
3. Return the path created

Do not invent paths.
""",
    tools=[prepare_project_workspace],
)


# ----------------------------
# Tech Lead Agent (Main)
# ----------------------------

tech_lead_agent = Agent(
    name="tech_lead_agent",
    model=ADK_MODEL,
    description="Main coordinator agent.",
    instruction="""
You are the Tech Lead Agent.

Responsibilities:

1. Check memory
2. Plan tasks
3. Delegate research if needed
4. ALWAYS delegate to scrum_master_agent when deadline exists
5. Delegate to workspace_prep_agent when project setup is needed
6. Save decisions into memory

Workflow order:

memory → research → scrum → workspace → summary
""",
    tools=memory_tools_phase3,
    sub_agents=[
        research_agent,
        scrum_master_agent,
        workspace_prep_agent,
    ],
)