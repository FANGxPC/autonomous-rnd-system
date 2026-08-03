import json
import os
from typing import Any, Dict, List, Optional

PROJECT_FILE = "projects.json"


def load_projects() -> Dict[str, Any]:
    """Load all stored projects from the local JSON file.

    Returns:
        Dict[str, Any]: Mapping of project keys to project data objects.
    """
    if not os.path.exists(PROJECT_FILE):
        return {}
    with open(PROJECT_FILE, "r") as f:
        return json.load(f)


def save_projects(data: Dict[str, Any]) -> None:
    """Save all projects dictionary to the local JSON file.

    Args:
        data (Dict[str, Any]): Project data dictionary to serialize.
    """
    with open(PROJECT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def list_projects() -> List[str]:
    """List all available project keys.

    Returns:
        List[str]: List of project key identifiers.
    """
    data = load_projects()
    return list(data.keys())


def get_project(project_key: str) -> Optional[Dict[str, Any]]:
    """Retrieve data for a specific project key.

    Args:
        project_key (str): Unique key identifying the project.

    Returns:
        Optional[Dict[str, Any]]: The project data dictionary, or None if not found.
    """
    data = load_projects()
    return data.get(project_key)


def save_project(project_key: str, project_data: Dict[str, Any]) -> None:
    """Save or update project data for a given project key.

    Args:
        project_key (str): Unique key identifying the project.
        project_data (Dict[str, Any]): Project payload to store.
    """
    data = load_projects()
    data[project_key] = project_data
    save_projects(data)

