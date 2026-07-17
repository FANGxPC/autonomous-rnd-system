import json
import os

PROJECT_FILE = "projects.json"


def load_projects():

    if not os.path.exists(PROJECT_FILE):

        return {}

    with open(PROJECT_FILE, "r") as f:

        return json.load(f)


def save_projects(data):

    with open(PROJECT_FILE, "w") as f:

        json.dump(data, f, indent=2)


def list_projects():

    data = load_projects()

    return list(data.keys())


def get_project(project_key):

    data = load_projects()

    return data.get(project_key)


def save_project(project_key, project_data):

    data = load_projects()

    data[project_key] = project_data

    save_projects(data)
