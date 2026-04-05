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
# Mock Workspace Tool
# ----------------------------

def mock_prepare_workspace(project_name: str) -> str:
    return f"[MOCK] Workspace prepared for project '{project_name}'"


# ----------------------------
# Research Agent
# ----------------------------

research_agent = Agent(
    name="research_agent",
    model="gemini-2.5-flash",
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
    model="gemini-2.5-flash",
    description="Creates tasks and schedules work.",
    instruction="""
You are the Scrum Master Agent.

Your responsibilities:
- Break the project into actionable tasks
- Create tickets for each task
- Keep timelines realistic

Always use the mock_create_ticket tool.
""",
    tools=[mock_create_ticket],
)


# ----------------------------
# Workspace Prep Agent (NEW - Sub-Agent 3)
# ----------------------------

workspace_prep_agent = Agent(
    name="workspace_prep_agent",
    model="gemini-2.5-flash",
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
    model="gemini-2.5-flash",
    description="Main coordinator agent.",
    instruction="""
You are the Tech Lead Agent.

Your responsibilities:

1. Check project memory using database tools
2. Break project into phases
3. Delegate research to Research Agent
4. Delegate planning to Scrum Master Agent
5. Delegate workspace setup to Workspace Prep Agent
6. Save decisions into memory

Always coordinate all sub-agents properly.
""",
    tools=memory_tools_phase3,
    sub_agents=[
        research_agent,
        scrum_master_agent,
        workspace_prep_agent
    ],
)