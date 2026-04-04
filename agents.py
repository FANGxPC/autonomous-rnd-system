"""
MEMBER 1 base + MEMBER 2 MCP tool integration
Member 2 replaced mock_create_ticket with real Notion + Calendar tools
"""

import os
from dotenv import load_dotenv
from google.adk.agents import Agent

# Member 3's Firebase memory tools (unchanged)
from database import memory_tools_phase3

# Member 2's real MCP tools (replacing the mocks)
from notion_tool   import create_kanban_card, list_kanban_cards
from calendar_tool import create_calendar_block, get_free_slots

load_dotenv()

# ----------------------------
# Mock Research Tool (Member 1 - unchanged)
# ----------------------------
def mock_search_arxiv(query: str) -> str:
    return f"[MOCK] Found research papers related to '{query}'"

# ----------------------------
# Research Agent (Member 1 - unchanged)
# ----------------------------
research_agent = Agent(
    name="research_agent",
    model="gemini-2.5-flash",
    description="Finds research papers and datasets.",
    instruction="""
    You are the Research Agent.
    When given a technical topic, search for relevant papers and datasets.
    Always use the mock_search_arxiv tool.
    """,
    tools=[mock_search_arxiv],
)

# ----------------------------
# Scrum Master Agent
# MEMBER 2: replaced mock_create_ticket with real Notion + Calendar tools
# ----------------------------
scrum_master_agent = Agent(
    name="scrum_master_agent",
    model="gemini-2.5-flash",
    description="Creates real Kanban cards in Notion and blocks Deep Work time on Google Calendar.",
    instruction="""
    You are the Scrum Master Agent.

    When given a project and deadline, you MUST:
    1. Call get_free_slots to find available time slots on the target date.
    2. Call create_calendar_block for the first 2-3 tasks to block Deep Work time.
    3. Call create_kanban_card for EACH task with: title, status='To Do', deadline, description.
    4. Return a summary listing every card created and every calendar block scheduled.

    Always create calendar blocks BEFORE Notion cards so deadlines are confirmed first.
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
# Tech Lead Agent (Member 1 - unchanged, just passes sub-agents)
# ----------------------------
tech_lead_agent = Agent(
    name="tech_lead_agent",
    model="gemini-2.5-flash",
    description="Main coordinator agent.",
    instruction="""
    You are the Tech Lead Agent.
    Your responsibilities:
    1. Check project memory using database tools
    2. Break project into phases
    3. Delegate research to Research Agent
    4. Delegate planning AND scheduling to Scrum Master Agent
    5. Save decisions into memory
    """,
    tools=memory_tools_phase3,
    sub_agents=[research_agent, scrum_master_agent],
)

print("✅ Member 2 MCP tools wired into scrum_master_agent!")
print("   Real tools: create_kanban_card, list_kanban_cards, create_calendar_block, get_free_slots")