"""
MEMBER 3 - MEMORY ARCHITECT (Phase 1)
File: database.py
Database: Firebase Firestore (cloud, persistent)
"""

import os
from datetime import datetime
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()

# ====================== FIREBASE INITIALIZATION ======================
# Initialize only once
if not firebase_admin._apps:
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path or not os.path.exists(cred_path):
        raise FileNotFoundError("❌ Service account JSON not found. Check GOOGLE_APPLICATION_CREDENTIALS in .env")
    
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase Admin SDK initialized successfully!")

db = firestore.client()


# ====================== CORE FUNCTIONS ======================

def save_project_context(project_key: str, category: str, value: str, notes: str = "") -> str:
    """
    Save data to Firestore (append-only style - keeps history)
    Example categories: "requirements", "research", "deadline", "tasks"
    """
    try:
        timestamp = datetime.now().isoformat()
        doc_ref = db.collection("project_memory").document()
        
        doc_ref.set({
            "project_key": project_key,
            "category": category,
            "value": value,
            "notes": notes,
            "timestamp": timestamp
        })
        
        success_msg = f"💾 SAVED to Firestore → [{category}] {project_key}"
        print(success_msg)
        return success_msg
    except Exception as e:
        error_msg = f"❌ Save Error: {str(e)}"
        print(error_msg)
        return error_msg


def retrieve_context(project_key: str, category: str = None) -> str:
    """
    Retrieve memory from Firestore.
    If category is given → only that category.
    Otherwise → all categories for the project.
    """
    try:
        query = db.collection("project_memory").where("project_key", "==", project_key)
        
        if category:
            query = query.where("category", "==", category)
        
        docs = query.order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        
        results = list(docs)
        if not results:
            return f"No memory found for project: {project_key}"
        
        output = f"📖 FIRESTORE MEMORY FOR: {project_key}\n"
        output += "=" * 60 + "\n"
        
        for doc in results:
            data = doc.to_dict()
            ts = data["timestamp"][:19]
            cat = data["category"].upper()
            val = data["value"]
            notes = data.get("notes", "")
            
            output += f"[{ts}] {cat}: {val}\n"
            if notes:
                output += f"   Notes: {notes}\n"
            output += "-" * 50 + "\n"
        
        print(output)
        return output
    except Exception as e:
        return f"❌ Retrieve Error: {str(e)}"


def log_agent_action(agent_name: str, action: str, details: str):
    """Log what agents do (for debugging)"""
    try:
        timestamp = datetime.now().isoformat()
        db.collection("action_logs").document().set({
            "agent_name": agent_name,
            "action": action,
            "details": details,
            "timestamp": timestamp
        })
        print(f"📝 Logged: {agent_name} - {action}")
    except:
        pass


def log_run_history(summary: str, prompt: str = ""):
    """Optional: Log full pipeline runs (useful for Member 4)"""
    try:
        timestamp = datetime.now().isoformat()
        db.collection("run_history").document().set({
            "timestamp": timestamp,
            "prompt": prompt,
            "summary": summary
        })
        print(f"📊 Run history logged")
    except:
        pass


# ====================== SELF-TEST ======================
def run_test():
    print("\n🧪 Running Firebase Memory Test...\n")
    project = "verilog_alu_demo"
    
    save_project_context(project, "requirements", "Design 16-bit RISC processor with ALU in Verilog", "Must be pipelined")
    save_project_context(project, "deadline", "2026-04-30", "Final hackathon submission")
    save_project_context(project, "research", "https://arxiv.org/pdf/2305.12345.pdf", "Good RISC-V ALU reference")
    
    print("\nRetrieving full memory:")
    retrieve_context(project)
    
    print("\nRetrieving only deadline:")
    retrieve_context(project, "deadline")
    
    log_agent_action("Tech_Lead", "saved_requirements", "User wants pipelined design")
    log_run_history("Test run completed successfully", "Design 16-bit ALU")
    
    print("\n✅ All tests passed! Check Firebase console to see the documents.")


if __name__ == "__main__":
    run_test()

# ====================== PHASE 2: ADK TOOL WRAPPERS ======================
# Plain functions work as tools: LlmAgent wraps callables with FunctionTool.

def save_project_context_tool(
    project_key: str, 
    category: str, 
    value: str, 
    notes: str = ""
) -> str:
    """
    Save project data to Firebase Firestore.
    Use this tool when you want the team to remember requirements, research, deadlines, etc.
    """
    return save_project_context(project_key, category, value, notes)


def retrieve_context_tool(
    project_key: str, 
    category: str = None
) -> str:
    """
    Retrieve memory from Firebase Firestore.
    If category is provided, returns only that category. 
    Otherwise returns all memory for the project.
    """
    return retrieve_context(project_key, category)


def log_agent_action_tool(
    agent_name: str, 
    action: str, 
    details: str
) -> str:
    """
    Log agent actions for debugging and tracking.
    """
    log_agent_action(agent_name, action, details)
    return f"✅ Action logged: {agent_name} - {action}"


def log_run_history_tool(
    summary: str, 
    prompt: str = ""
) -> str:
    """
    Log the full pipeline run (useful for Member 4 backend).
    """
    log_run_history(summary, prompt)
    return "✅ Run history saved to Firestore"


# ====================== EXPORT FOR MEMBER 1 ======================
memory_tools = [
    save_project_context_tool,
    retrieve_context_tool,
    log_agent_action_tool,
    log_run_history_tool
]

print("✅ Member 3 Phase 2 Complete!")
print("Member 1 can now import:")
print("   from database import memory_tools")
print("Then add: tools=memory_tools  to Tech_Lead agent")

# ====================== PHASE 3: ADVANCED FEATURES & POLISH ======================

def list_all_projects() -> str:
    """List all unique project_keys in memory (useful for Tech Lead)"""
    try:
        docs = db.collection("project_memory").stream()
        projects = set()
        for doc in docs:
            data = doc.to_dict()
            if "project_key" in data:
                projects.add(data["project_key"])
        
        if not projects:
            return "No projects found in memory yet."
        
        output = "📋 AVAILABLE PROJECTS IN MEMORY:\n"
        output += "=" * 50 + "\n"
        for p in sorted(projects):
            output += f"• {p}\n"
        return output
    except Exception as e:
        return f"❌ Error listing projects: {str(e)}"


def clear_project_memory(project_key: str, category: str = None) -> str:
    """Delete memory for a specific project or category"""
    try:
        query = db.collection("project_memory").where("project_key", "==", project_key)
        if category:
            query = query.where("category", "==", category)
        
        docs = query.stream()
        deleted_count = 0
        for doc in docs:
            doc.reference.delete()
            deleted_count += 1
        
        return f"🗑️ Deleted {deleted_count} documents for project: {project_key}"
    except Exception as e:
        return f"❌ Clear Error: {str(e)}"


def get_memory_summary(project_key: str) -> str:
    """Get a clean summary of all categories for a project"""
    try:
        docs = db.collection("project_memory").where("project_key", "==", project_key)\
                .order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        
        summary = {}
        for doc in docs:
            data = doc.to_dict()
            cat = data["category"]
            if cat not in summary:
                summary[cat] = data["value"]
        
        output = f"📊 MEMORY SUMMARY FOR: {project_key}\n"
        output += "=" * 50 + "\n"
        for cat, val in summary.items():
            output += f"• {cat.upper()}: {val[:120]}{'...' if len(val) > 120 else ''}\n"
        return output
    except Exception as e:
        return f"❌ Summary Error: {str(e)}"


# ====================== IMPROVED ERROR HANDLING ======================

def safe_save_project_context(project_key: str, category: str, value: str, notes: str = "") -> str:
    """Safe version with retry (recommended for agents)"""
    for attempt in range(3):
        try:
            return save_project_context(project_key, category, value, notes)
        except Exception as e:
            if attempt == 2:
                return f"❌ Failed after 3 attempts: {str(e)}"
            import time
            time.sleep(1)


# ====================== FINAL EXPORTS ======================
memory_tools_phase3 = [
    save_project_context_tool,
    retrieve_context_tool,
    log_agent_action_tool,
    log_run_history_tool,
    list_all_projects,
    clear_project_memory,
    get_memory_summary
]

print("✅ Member 3 Phase 3 Complete!")
print("Advanced tools added: list_all_projects, clear_project_memory, get_memory_summary")
print("Use memory_tools_phase3 for full feature set")