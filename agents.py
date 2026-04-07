"""
ADK agents: Tech Lead (Firestore) + Research (web + optional arXiv) + Scrum (Notion + Calendar) + Workspace Prep.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent

from calendar_tool import create_calendar_block, spread_task_dates
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

When given a project and a **deadline** (plan end date) in the user message, you MUST **spread work in time**:

1. Decide how many concrete tasks you will create (typically 4–8; each gets a card + calendar block).
2. Call **spread_task_dates** with `plan_end_date` = that deadline (YYYY-MM-DD) and `num_tasks` = that count.
3. For **each** task **i** (1-based) in order, using date **D_i** from that list:
   a. Do **not** call get_free_slots — unnecessary and slow.
   b. Call **create_calendar_block** with `date=D_i`, this task’s title, `duration_hours=2`, and **start_hour**
      from: 1→10, 2→14, 3→16, 4→11, 5→15, 6→9, 7→17, 8→13 (repeat for 9+).
   c. Call **create_kanban_card** with **deadline=D_i** (same ISO date as that calendar block).
4. Card fields (every task):
   - title: short, action-oriented
   - status='To Do'
   - deadline: **must match** **D_i** for that task’s calendar block
   - description: **substantial** (at least 4–8 sentences or bullet blocks) including:
     • What "done" looks like (acceptance criteria)
     • Dependencies or prerequisites
     • Suggested sub-steps or files/modules to touch
     • Risks or open questions
     Format bullets as lines starting with `* ` or `- ` so Notion shows real bullet lists; use **Label**:
     for sub-headings inside bullets. Do NOT use one-line descriptions.
   - sources: newline-separated list of **URLs and paper titles** copied from research_agent / web /
     arXiv tool output (2–8 lines). Each line should include the http/https URL when available.
     This appears under **Sources & references** at the bottom of the card. Use the SAME sources
     across tasks for this run when they all apply, or the subset relevant to each task.

5. Return a summary listing every card and every calendar block with **its date**.

Always create each **calendar block** before its matching **Notion** card.
Use status 'To Do' for all new tasks.
""",
    tools=[
        spread_task_dates,
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
