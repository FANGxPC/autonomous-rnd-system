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


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\s\-]+", "", (name or "").strip())
    s = re.sub(r"\s+", "_", s)[:80]
    return s or "project"


def prepare_project_workspace(project_name: str, short_summary: str = "") -> str:
    """
    Create a directory under WORKSPACE_OUTPUT_DIR with docs/, src/, and README.md.

    Args:
        project_name: Human-readable name (used for folder slug and README title).
        short_summary: Optional one-line description for README.

    Returns:
        Absolute path and confirmation text (or error string).
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
    except OSError as e:
        return f"❌ Workspace: could not create directories: {e}"

    readme = base / "README.md"
    summary_line = (short_summary or "").strip() or "Starter layout from the Autonomous R&D pipeline."
    body = f"""# {name}

{summary_line}

## Layout

- `src/` — application or experiment code
- `docs/` — notes, design, API sketches

Generated automatically; safe to edit or delete.
"""
    try:
        readme.write_text(body, encoding="utf-8")
    except OSError as e:
        return f"❌ Workspace: could not write README: {e}"

    return (
        f"✅ Workspace ready at `{base}`\n"
        f"   Created: README.md, docs/, src/"
    )
