import asyncio
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

from agents import tech_lead_agent

from project_store import (
    list_projects,
    get_project,
    save_project
)


async def main():

    session_service = InMemorySessionService()

    runner = Runner(
        agent=tech_lead_agent,
        app_name="autonomous_rnd_system",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="autonomous_rnd_system",
        user_id="test_user",
    )

    # -------------------------
    # SHOW PROJECTS
    # -------------------------

    projects = list_projects()

    print("\nAvailable Projects:")

    if not projects:

        print("No projects found.")

    else:

        for i, p in enumerate(projects, start=1):

            print(f"{i} - {p}")

    print("\nSelect mode:")
    print("1 - New Project")
    print("2 - Refine Existing Project")

    choice = input("Enter choice: ")

    # -------------------------
    # NEW PROJECT
    # -------------------------

    if choice == "1":

        prompt = input("\nEnter new project description: ")

        project_key = prompt.lower().replace(" ", "_")

        mode = "new_project"

    else:

        if not projects:

            print("No projects to refine.")

            return

        index = int(input("\nSelect project number: ")) - 1

        project_key = projects[index]

        prompt = input("\nEnter refinement request: ")

        mode = "refinement"

    print("\nMODE:", mode)
    print("PROJECT:", project_key)

    # -------------------------
    # LOAD EXISTING PROJECT
    # -------------------------

    existing_project = get_project(project_key)

    if existing_project:

        print("\nLoaded existing project.")

    # -------------------------
    # SEND TO AGENT
    # -------------------------

    content = types.Content(
        role="user",
        parts=[
            types.Part(
                text=f"""
Project Key: {project_key}

Mode: {mode}

Existing Project:
{existing_project}

User Request:
{prompt}
"""
            )
        ]
    )

    print("\n" + "=" * 50)
    print("RUNNING AGENT CHAIN...")
    print("=" * 50 + "\n")

    response_text = ""

    async for event in runner.run_async(

        user_id="test_user",
        session_id=session.id,
        new_message=content,

    ):

        author = event.author or "system"

        if event.content and event.content.parts:

            for part in event.content.parts:

                if part.text:

                    print(f"[{author}]: {part.text}")

                    response_text += part.text

    # -------------------------
    # SAVE PROJECT
    # -------------------------

    project_data = {

        "last_response": response_text

    }

    save_project(project_key, project_data)

    print("\nProject saved.")


if __name__ == "__main__":

    asyncio.run(main())
