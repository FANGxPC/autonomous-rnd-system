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

Your responsibilities:

1. Read existing project memory using the project_key.
2. Break the project into concrete tasks.
3. Assign each task to a specific team member.

You MUST always:

- Assign responsibility to a named team member.
- Ensure every task has an owner.
- Avoid duplicate task creation.
- Use previous plan context when refining.

TEAM MEMBERS EXAMPLE:

Backend Engineer — Rahul  
Frontend Engineer — Aisha  
QA Engineer — Dev  

When generating tasks, include:

Task Title  
Assigned To  
Description  
Acceptance Criteria  
Dependencies  
Risks  
Estimated Time  

If this is a refinement request:

You MUST:

- Identify what changed
- Update only affected tasks
- Keep existing tasks unchanged
- Do NOT recreate everything

Workflow order:

memory → research → scrum → workspace → summary

OUTPUT FORMAT RULE (MANDATORY):

Every task MUST be printed using this structure:

Task Title:
Assigned To:
Description:
Acceptance Criteria:
Dependencies:
Risks:
Estimated Time:

Never omit the "Assigned To" field.
Never output tasks as plain bullet points.

REFINEMENT DETECTION RULE:

If the user's request modifies an existing project, you MUST:

1. Compare the new request with stored project memory
2. Identify exactly what changed
3. Update only the affected tasks
4. Keep unchanged tasks intact
5. Clearly state which tasks were modified, added, or removed

Never regenerate the entire plan unless explicitly requested.

REFINEMENT REPORTING RULE (MANDATORY):

If this request modifies an existing project, you MUST produce a refinement summary before listing tasks.

Always display:

Modified Tasks:
- List tasks that changed

Added Tasks:
- List new tasks created

Unchanged Tasks:
- List tasks that remain the same

Then provide the full updated task list.

Never skip this classification step.
""",
    tools=memory_tools_phase3,
    sub_agents=[
        research_agent,
        scrum_master_agent,
        workspace_prep_agent,
    ],
)