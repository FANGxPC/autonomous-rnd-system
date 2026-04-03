import os
from dotenv import load_dotenv
from google.adk.agents import Agent

# Import database memory tools created by Member 3
from database import memory_tools_phase3

load_dotenv()

# gemini-2.0-flash often shows free-tier quota "0" for new keys; 2.5-flash usually has a small free allowance.
ADK_MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")

# LITE mode: one agent, all tools, no sub-agents → far fewer generateContent calls (survives free tier).
# Set ADK_LITE=0 in .env for full Tech Lead → Research → Scrum graph (needs higher quota / billing).
ADK_LITE = os.getenv("ADK_LITE", "1").strip().lower() in ("1", "true", "yes", "on")

# ----------------------------
# Mock Research Tool
# ----------------------------


def mock_search_arxiv(query: str) -> str:
    return f"[MOCK] Found research papers related to '{query}'"


# ----------------------------
# Mock Task Tool
# ----------------------------


def mock_create_ticket(title: str, description: str, deadline: str) -> str:
    return f"[MOCK] Ticket created: '{title}' due {deadline}"


_MOCK_TOOLS = [mock_search_arxiv, mock_create_ticket]

# ----------------------------
# Sub-agents (full pipeline only)
# ----------------------------

research_agent = Agent(
    name="research_agent",
    model=ADK_MODEL,
    description="Finds research papers and datasets.",
    instruction="""
    You are the Research Agent.
    When given a technical topic, search for relevant papers and datasets.
    Always use the mock_search_arxiv tool once.
    """,
    tools=[mock_search_arxiv],
)

scrum_master_agent = Agent(
    name="scrum_master_agent",
    model=ADK_MODEL,
    description="Creates tasks and schedules work.",
    instruction="""
    You are the Scrum Master Agent.
    Break work into actionable items and create tickets with mock_create_ticket.
    For demos and rate limits: create at most 4 tickets total per request (group related work).
    """,
    tools=[mock_create_ticket],
)

# ----------------------------
# Tech Lead (root)
# ----------------------------

_INSTRUCTION_FULL = """
    You are the Tech Lead Agent.

    Your responsibilities:
    1. Check project memory using database tools
    2. Break project into phases
    3. Delegate research to Research Agent
    4. Delegate planning to Scrum Master Agent
    5. Save decisions into memory
    """

_INSTRUCTION_LITE = """
    You are the Tech Lead Agent (LITE pipeline — no sub-agent handoffs).

    Do the minimum steps, each tool at most once unless save needs two rows:
    1. save_project_context: category "requirements", value = user goal, notes if any.
    2. save_project_context: category "deadline", value = deadline from the message.
    3. retrieve_context for the given project_key (no category filter).
    4. mock_search_arxiv once with a short query derived from the prompt.
    5. save_project_context: category "research", value = the mock search result string.
    6. mock_create_ticket at most 2 times for the two biggest milestones (same deadline).
    Then answer with a brief markdown summary of what you stored and planned.
    """

if ADK_LITE:
    tech_lead_agent = Agent(
        name="tech_lead_agent",
        model=ADK_MODEL,
        description="Main coordinator (lite: single agent, minimal API calls).",
        instruction=_INSTRUCTION_LITE,
        tools=memory_tools_phase3 + _MOCK_TOOLS,
        sub_agents=[],
    )
else:
    tech_lead_agent = Agent(
        name="tech_lead_agent",
        model=ADK_MODEL,
        description="Main coordinator agent.",
        instruction=_INSTRUCTION_FULL,
        tools=memory_tools_phase3,
        sub_agents=[research_agent, scrum_master_agent],
    )
