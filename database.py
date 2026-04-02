"""
MEMBER 3 - MEMORY ARCHITECT
File: database.py
Purpose: Persistent memory for the entire multi-agent system using SQLite
"""

import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# ====================== DATABASE SETUP ======================
# Connect to SQLite database (creates the file if it doesn't exist)
DB_NAME = "project_memory.db"
conn = sqlite3.connect(DB_NAME, check_same_thread=False)  # Allow access from agents
cursor = conn.cursor()

# Create the main memory table (project_key e.g. "alu_verilog_2026";
# category e.g. requirements/research/tasks/deadline; value can be JSON)
cursor.execute('''
CREATE TABLE IF NOT EXISTS project_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    project_key TEXT UNIQUE,
    category TEXT,
    value TEXT NOT NULL,
    notes TEXT
)
''')

# Create another table for action logs (useful for debugging)
cursor.execute('''
CREATE TABLE IF NOT EXISTS action_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent_name TEXT,
    action TEXT,
    details TEXT
)
''')

conn.commit()

print(f"✅ Database initialized successfully! File: {DB_NAME}")
print("Tables created: project_memory + action_logs\n")


# ====================== CORE FUNCTIONS ======================

def save_project_context(project_key: str, category: str, value: str, notes: str = "") -> str:
    """
    Save important information to memory.
    
    Example:
    save_project_context("alu_project", "requirements", "16-bit RISC processor in Verilog", "User wants pipelined design")
    """
    try:
        timestamp = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT OR REPLACE INTO project_memory 
            (timestamp, project_key, category, value, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (timestamp, project_key, category, value, notes))
        
        conn.commit()
        
        success_msg = f"💾 SAVED → [{category}] {project_key}"
        print(success_msg)
        return success_msg
        
    except Exception as e:
        error_msg = f"❌ Save Error: {str(e)}"
        print(error_msg)
        return error_msg


def retrieve_context(project_key: str, category: str = None) -> str:
    """
    Get information from memory.
    
    If category is given, returns only that category.
    Otherwise returns all data for the project.
    """
    try:
        if category:
            cursor.execute("""
                SELECT timestamp, category, value, notes 
                FROM project_memory 
                WHERE project_key = ? AND category = ?
                ORDER BY timestamp DESC
            """, (project_key, category))
        else:
            cursor.execute("""
                SELECT timestamp, category, value, notes 
                FROM project_memory 
                WHERE project_key = ?
                ORDER BY timestamp DESC
            """, (project_key,))
        
        results = cursor.fetchall()
        
        if not results:
            return f"No memory found for project: {project_key}"
        
        output = f"📖 MEMORY FOR PROJECT: {project_key}\n"
        output += "=" * 50 + "\n"
        
        for row in results:
            ts, cat, val, notes = row
            output += f"[{ts[:19]}] {cat.upper()}: {val}\n"
            if notes:
                output += f"   Notes: {notes}\n"
            output += "-" * 40 + "\n"
        
        print(output)
        return output
        
    except Exception as e:
        return f"❌ Retrieve Error: {str(e)}"


def log_agent_action(agent_name: str, action: str, details: str):
    """Record what each agent did (good for debugging)"""
    try:
        timestamp = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO action_logs (timestamp, agent_name, action, details)
            VALUES (?, ?, ?, ?)
        """, (timestamp, agent_name, action, details))
        conn.commit()
        print(f"📝 Logged action: {agent_name} - {action}")
    except:
        pass  # Don't crash if logging fails


# ====================== TEST FUNCTION ======================
def run_test():
    """Test the memory system"""
    print("\n🧪 Running Memory System Test...\n")
    
    project = "verilog_alu_demo"
    
    save_project_context(
        project_key=project,
        category="requirements",
        value="Design 16-bit RISC processor with ALU in Verilog",
        notes="Must be synthesizable and have testbench"
    )
    
    save_project_context(
        project_key=project,
        category="deadline",
        value="2026-04-30",
        notes="Final submission date"
    )
    
    save_project_context(
        project_key=project,
        category="research",
        value="https://arxiv.org/pdf/2305.12345.pdf - RISC-V architecture paper",
        notes="Good reference for ALU design"
    )
    
    # Retrieve everything
    print("\nRetrieving full memory...")
    retrieve_context(project)
    
    log_agent_action("Tech_Lead", "saved_requirements", "User wants pipelined ALU")


# Run test when file is executed directly
if __name__ == "__main__":
    run_test()
