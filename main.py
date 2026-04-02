from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agents import tech_lead_agent
import inspect # 👈 ADD THIS AT THE VERY TOP OF MAIN.PY
import asyncio

# --- FUTURE IMPORTS FROM YOUR TEAM ---
# from agents import tech_lead_agent  (From M1)
# from database import log_run      (From M3)

# ADK Imports (Assuming M1 provides the configured agent)
from google.adk.runners import Runner 
from google.adk.sessions import InMemorySessionService  

app = FastAPI(title="FlowState API")

# Define the input payload structure from Postman
class ProjectRequest(BaseModel):
    project_prompt: str
    github_repo_link: str | None = None


@app.get("/")
def read_root():
    return {"message": "Welcome to the FlowState API. Send POST requests to /trigger-pipeline"}



@app.post("/trigger-pipeline")
async def trigger_pipeline(request: ProjectRequest):
    try:
        print(f"🚀 INCOMING REQUEST: Starting pipeline for: {request.project_prompt}")
        
        # 1. Initialize the Session Service
        session_service = InMemorySessionService()
        
        # 2. Create the session 
        current_session = await session_service.create_session(app_name="flowstate_demo", user_id="demo_user")
        
        # 3. Initialize the Runner
        runner = Runner(app_name="flowstate_demo", agent=tech_lead_agent, session_service=session_service)
        
        # 4. Fire the Runner with the formatted Content dictionary
        event_stream = runner.run_async(
            user_id="demo_user",
            session_id=current_session.id,
            new_message={"role": "user", "parts": [{"text": request.project_prompt}]}
        )
        
        # 5. Loop through the AsyncGenerator to capture the agents working
        final_summary = ""
        async for event in event_stream:
            # This prints the raw agent communication directly to your Cloud Shell terminal!
            print("🤖 AGENT EVENT:", event)
            
            # Extract the text from the event if it exists to send back to Postman/Swagger
            if hasattr(event, 'text') and event.text:
                final_summary += event.text
            elif hasattr(event, 'message') and hasattr(event.message, 'text'):
                final_summary += event.message.text
        
        # 6. Return the gathered response
        return {
            "status": "Pipeline Completed",
            "summary": final_summary or "Success! Check your terminal for the detailed agent logs."
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

         
@app.get("/health")
def health_check():
    return {"status": "FlowState Backend is Live 🟢"}