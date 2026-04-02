import os
from dotenv import load_dotenv
from google.adk.agents import Agent

# Import database memory tools created by Member 3
from database import memory_tools_phase3

load_dotenv()


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


# ----------------------------
# Research Agent
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
# ----------------------------

scrum_master_agent = Agent(
    name="scrum_master_agent",
    model="gemini-2.5-flash",
    description="Creates tasks and schedules work.",
    instruction="""
    You are the Scrum Master Agent.
    Break tasks into actionable items and create tickets.
    """,
    tools=[mock_create_ticket],
)


# ----------------------------
# Tech Lead Agent (Main Manager)
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
    4. Delegate planning to Scrum Master Agent
    5. Save decisions into memory
    """,
    tools=memory_tools_phase3,
    sub_agents=[research_agent, scrum_master_agent],
)