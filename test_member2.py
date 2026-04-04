"""
Member 2 deliverable test:
Proves the ADK agent can physically create a Kanban card AND a Calendar block.
"""

import asyncio
from datetime import datetime
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from agents import scrum_master_agent

APP_NAME = "autonomous-rnd-system"
USER_ID  = "member2-test"

async def test_scrum_master():
    print("\n" + "="*60)
    print("🧪 MEMBER 2 DELIVERABLE TEST")
    print("="*60)

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )

    runner = Runner(
        agent=scrum_master_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    today = datetime.now().strftime("%Y-%m-%d")
    prompt = (
        f"Project: Build a 16-bit RISC processor in Verilog\n"
        f"Deadline: 2026-06-01\n"
        f"Today's date: {today}\n\n"
        "Please:\n"
        "1. Check free slots today\n"
        "2. Create a Deep Work calendar block for 'ALU Design' today at 3 PM\n"
        "3. Create a Notion card for 'ALU Design' with status 'To Do' and deadline 2026-05-20\n"
        "4. Create a Notion card for 'Register File Design' with status 'To Do' and deadline 2026-05-25\n"
        "5. Give me a summary of everything created."
    )

    print(f"\n📤 Sending to scrum_master_agent:\n{prompt}\n")

    message = Content(role="user", parts=[Part(text=prompt)])
    final_response = ""

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=message,
    ):
        if event.is_final_response():
            final_response = event.content.parts[0].text

    print("\n📥 Agent Response:")
    print(final_response)
    print("\n✅ Test complete! Check Notion board and Google Calendar to confirm.")

if __name__ == "__main__":
    asyncio.run(test_scrum_master())