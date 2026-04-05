"""
ADK agents: Tech Lead (Firestore) + Research (mock arxiv) + Scrum Master (Notion + Google Calendar) + Workspace Prep.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent

from calendar_tool import create_calendar_block, get_free_slots
from database import memory_tools_phase3
from notion_tool import create_kanban_card, list_kanban_cards

load_dotenv()

ADK_MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")
ADK_LITE = os.getenv("ADK_LITE", "0").strip().lower() in ("1", "true", "yes", "on")


# ----------------------------
# Mock Research Tool
# ----------------------------

def mock_search_arxiv(query: str) -> str:
    return f"[MOCK] Found research papers related to '{query}'"


# ----------------------------
# Mock Workspace Tool
# ----------------------------

def mock_prepare_workspace(project_name: str) -> str:
    return f"[MOCK] Workspace prepared for project '{project_name}'"


# ----------------------------
# Research Agent
# ----------------------------

research_agent = Agent(
    name="research_agent",
    model=ADK_MODEL,
    description="Finds research papers and datasets.",
    instruction="""
You are the Research Agent.

When given a technical topic:
- Search for relevant research papers
- Identify datasets
- Provide useful references

Always use the mock_search_arxiv tool.
Be concise and technical.
""",
    tools=[mock_search_arxiv],
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

1. Call get_free_slots to find available time slots on the target date.
2. Call create_calendar_block for the first 2-3 tasks to block Deep Work time.
3. Call create_kanban_card for EACH task with:
   - title
   - status='To Do'
   - deadline
   - description
4. Return a summary listing every card created and every calendar block scheduled.

Always create calendar blocks BEFORE Notion cards.
Use status 'To Do' for all new tasks.
""",
    tools=[
        get_free_slots,
        create_calendar_block,
        create_kanban_card,
        list_kanban_cards,
    ],
)


# ----------------------------
# Workspace Prep Agent (Sub-Agent 3)
# ----------------------------

workspace_prep_agent = Agent(
    name="workspace_prep_agent",
    model=ADK_MODEL,
    description="Prepares project workspace, README, and starter structure.",
    instruction="""
You are the Workspace Preparation Agent.

After planning is complete, your job is to:

1. Create a basic project folder structure
2. Draft a README file
3. Suggest initial files needed
4. Prepare starter documentation

Focus on practical developer setup.
Keep output structured and ready-to-use.
""",
    tools=[mock_prepare_workspace],
)


# ----------------------------
# Tech Lead Agent (Main Manager)
# ----------------------------

tech_lead_agent = Agent(
    name="tech_lead_agent",
    model=ADK_MODEL,
    description="Main coordinator agent.",
    instruction="""
You are the Tech Lead Agent.

Your responsibilities:

1. Check project memory using database tools
2. Break project into phases
3. Delegate research to Research Agent
4. Delegate planning and scheduling to Scrum Master Agent
5. Delegate workspace setup to Workspace Prep Agent
6. Save decisions into memory

Always coordinate all sub-agents properly.
""",
    tools=memory_tools_phase3,
    sub_agents=[
        research_agent,
        scrum_master_agent,
        workspace_prep_agent,
    ],
)