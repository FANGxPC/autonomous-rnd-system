"""
Create a real on-disk starter layout for a project (folders + README).
Output root is WORKSPACE_OUTPUT_DIR (default: generated_workspaces/).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def validate_workspace(base: Path) -> bool:
    """
    Validate that required workspace files exist.
    """
    required_items = [
        base / "README.md",
        base / "requirements.txt",
        base / "src" / "main.py",
        base / "docs",
    ]

    for item in required_items:
        if not item.exists():
            return False

    return True


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\s\-]+", "", (name or "").strip())
    s = re.sub(r"\s+", "_", s)[:80]
    return s or "project"


def generate_code_templates(base: Path, libraries: list[str]) -> list[str]:
    """
    Generate starter code files based on detected libraries.
    """

    created_files = []

    libs = [lib.lower() for lib in libraries]

    src = base / "src"

    # FastAPI support
    if "fastapi" in libs:
        main_file = src / "main.py"
        main_code = """from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "API running"}
"""
        try:
            main_file.write_text(main_code, encoding="utf-8")
        except OSError as e:
            return [f"❌ Workspace: could not write main.py: {e}"]

        created_files.append("src/main.py")

    # JWT support
    if any("jose" in lib for lib in libs):
        auth_file = src / "auth.py"
        auth_code = """from datetime import datetime, timedelta
from jose import jwt

SECRET_KEY = "change_me"
ALGORITHM = "HS256"

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
"""
        auth_file.write_text(auth_code, encoding="utf-8")
        created_files.append("src/auth.py")

    # Password hashing support
    if any("passlib" in lib for lib in libs):
        security_file = src / "security.py"
        security_code = """from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(password, hashed):
    return pwd_context.verify(password, hashed)
"""
        security_file.write_text(security_code, encoding="utf-8")
        created_files.append("src/security.py")

    # -------------------------
    # Database ORM support
    # -------------------------
    if any("sqlalchemy" in lib for lib in libs):
        models_file = src / "models.py"
        models_code = """from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
"""
        models_file.write_text(models_code, encoding="utf-8")
        created_files.append("src/models.py")

    # -------------------------
    # Database migration support
    # -------------------------
    if any("alembic" in lib for lib in libs):
        migrations_dir = base / "migrations"
        migrations_dir.mkdir(exist_ok=True)

        env_file = migrations_dir / "env.py"
        env_file.write_text(
            "# Alembic migration environment\n",
            encoding="utf-8"
        )

        created_files.append("migrations/env.py")

    # -------------------------
    # Cache support
    # -------------------------
    if any("redis" in lib for lib in libs):
        cache_file = src / "cache.py"
        cache_code = """import redis

def get_cache_client():
    return redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True
    )
"""
        cache_file.write_text(
            cache_code,
            encoding="utf-8"
        )
        created_files.append("src/cache.py")

    return created_files


def prepare_project_workspace(
    project_name: str,
    short_summary: str = "",
    num_teammates: int = 0,
    team_members: list[dict[str, str]] | None = None,
    libraries: list[str] | None = None
) -> str:
    """
    Create a directory under WORKSPACE_OUTPUT_DIR with docs/, src/, and README.md.
    Generates personalized sub-directories for each member if team details are provided.
    """
    name = (project_name or "").strip()
    if not name:
        return "❌ Workspace: project_name is empty."

    root_env = os.getenv("WORKSPACE_OUTPUT_DIR", "generated_workspaces").strip()
    root = Path(root_env).resolve()
    slug = _slug(name)
    base = root / slug

    try:
        base.mkdir(parents=True, exist_ok=True)
        (base / "docs").mkdir(exist_ok=True)
        (base / "src").mkdir(exist_ok=True)

        members_to_create = team_members or []
        if not members_to_create and num_teammates > 0:
            members_to_create = [
                {"name": f"Teammate {i+1}", "role": "Developer"}
                for i in range(num_teammates)
            ]

        if members_to_create:
            for member in members_to_create:
                m_name = _slug(member.get("name", "teammate"))
                m_dir = base / m_name
                m_dir.mkdir(exist_ok=True)

                m_readme = m_dir / "README.md"
                m_readme_content = (
                    f"# {member.get('name', 'Teammate')} Workspace\n\n"
                    f"Role: {member.get('role', 'Developer')}\n\n"
                    f"Personal workspace for {name}.\n"
                )
                m_readme.write_text(m_readme_content, encoding="utf-8")

                (m_dir / "notes.md").write_text(
                    "# Notes\n\n- Start adding your thoughts here.\n",
                    encoding="utf-8"
                )

    except OSError as e:
        return f"❌ Workspace: could not create directories: {e}"

    readme = base / "README.md"
    summary_line = (short_summary or "").strip() or "Starter layout from the Autonomous R&D pipeline."
    body = f"""# {name}

{summary_line}

## Layout

- `src/` — application or experiment code
- `docs/` — notes, design, API sketches
"""
    if members_to_create:
        body += "\n## Team Workspaces\n\n"
        for member in members_to_create:
            m_name = _slug(member.get("name", "teammate"))
            body += f"- `{m_name}/` — workspace for {member.get('name', 'Team Member')} ({member.get('role', 'Developer')})\n"

    body += "\nGenerated automatically; safe to edit or delete.\n"

    try:
        readme.write_text(body, encoding="utf-8")
    except OSError as e:
        return f"❌ Workspace: could not write README: {e}"

    # ----------------------------
    # Generate requirements.txt
    # ----------------------------
    requirements_file = base / "requirements.txt"
    libs = libraries if libraries else ["fastapi", "uvicorn", "pydantic"]

    try:
        requirements_file.write_text("\n".join(libs) + "\n", encoding="utf-8")
    except OSError as e:
        return f"❌ Workspace: could not write requirements.txt: {e}"

    # ----------------------------
    # Generate starter main.py
    # ----------------------------
    main_file = base / "src" / "main.py"
    main_code = """from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Project initialized successfully"}
"""
    try:
        main_file.write_text(main_code, encoding="utf-8")
    except OSError as e:
        return f"❌ Workspace: could not write main.py: {e}"

    # ----------------------------
    # Generate code templates
    # ----------------------------
    generated_files = generate_code_templates(
        base,
        libraries or []
    )

    confirm_msg = f"""
Workspace Status:
SUCCESS

Workspace Path:
{base}

Files Created:

- README.md
- requirements.txt
- docs/

Code Files:
{generated_files}

Validation Result:
{"PASSED" if validate_workspace(base) else "FAILED"}
"""
    if members_to_create:
        confirm_msg += f"\nTeam member subdirectories created: {len(members_to_create)}"
    return confirm_msg
