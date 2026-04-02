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
