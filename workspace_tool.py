"""
Create a real on-disk starter layout for a project (folders + README).
Output root is WORKSPACE_OUTPUT_DIR (default: generated_workspaces/).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
# Global state dictionary safely passes the generated URL back to the main request thread across asyncio task boundaries
global_workspace_urls: dict[str, str] = {}


def _slug(name: str | None) -> str:
    """Sanitize and format a string into a filesystem-safe directory slug.

    Args:
        name: Name string to be converted into a slug.

    Returns:
        Cleaned slug string truncated to a maximum of 80 characters.
    """
    s = re.sub(r"[^\w\s\-]+", "", (name or "").strip())
    s = re.sub(r"\s+", "_", s)[:80]
    return s or "project"


def prepare_project_workspace(project_name: str, short_summary: str = "", num_teammates: int = 0, team_members: list[dict[str, str]] | None = None) -> str:
    """
    Create a directory under WORKSPACE_OUTPUT_DIR with docs/, src/, and README.md.
    Generates personalized sub-directories for each member if team details are provided.

    Args:
        project_name: Human-readable name (used for folder slug and README title).
        short_summary: Optional one-line description for README.
        num_teammates: The number of team members down for the project.
        team_members: Optional list of team member objects, e.g. [{"name": "Alice", "role": "Backend"}].

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
        
        # Create per-user folders fallback to num_teammates if needed
        members_to_create = team_members or []
        if not members_to_create and num_teammates > 0:
            members_to_create = [{"name": f"Teammate {member_index+1}", "role": "Developer"} for member_index in range(num_teammates)]
            
        if members_to_create:
            for member in members_to_create:
                member_slug = _slug(member.get("name", "teammate"))
                member_dir = base / member_slug
                member_dir.mkdir(exist_ok=True)
                
                member_role = member.get("role", "Developer").lower()
                member_readme = member_dir / "README.md"
                member_readme_content = f"# {member.get('name', 'Teammate')} Workspace\n\nRole: {member.get('role', 'Developer')}\n\nPersonal workspace for {name}.\n"
                member_readme.write_text(member_readme_content, encoding="utf-8")
                
                # Generic text file for their notes
                (member_dir / "notes.md").write_text("# Notes\n\n- Start adding your thoughts here.\n", encoding="utf-8")

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
            member_slug = _slug(member.get("name", "teammate"))
            body += f"- `{member_slug}/` — workspace for {member.get('name', 'Team Member')} ({member.get('role', 'Developer')})\n"

    body += "\nGenerated automatically; safe to edit or delete.\n"
    
    try:
        readme.write_text(body, encoding="utf-8")
    except OSError as e:
        return f"❌ Workspace: could not write README: {e}"

    try:
        import shutil
        zip_path = shutil.make_archive(str(base), 'zip', str(base))
    except Exception as e:
        return f"❌ Workspace: generated folder but could not zip it: {e}"

    download_link = f"/api/download-workspace/{slug}.zip"
    
    # ── Upload to Google Cloud Storage (if configured) ──
    gcs_bucket = os.getenv("WORKSPACE_GCS_BUCKET", "").strip()
    if gcs_bucket:
        try:
            from google.cloud import storage
            from datetime import timedelta
            
            client = storage.Client()
            bucket = client.bucket(gcs_bucket)
            blob = bucket.blob(f"generated_workspaces/{slug}.zip")
            blob.upload_from_filename(f"{base}.zip")
            
            # Generate a Signed URL valid for 7 days
            download_link = blob.generate_signed_url(version="v4", expiration=timedelta(days=7), method="GET")
        except Exception as e:
            return f"❌ Workspace: Zipped locally but GCS upload failed: {e}"

    # Store in global state so main.py can grab it flawlessly across thread boundaries
    global_workspace_urls[slug] = download_link

    confirm_msg = f"✅ Workspace zipped and ready for download: {download_link}\n   Contents: README.md, docs/, src/"
    if members_to_create:
        confirm_msg += f", and {len(members_to_create)} team member subdirectories."
    return confirm_msg

