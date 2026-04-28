import os


def validate_requirements(required_libraries: list) -> str:
    """
    Checks whether required libraries exist in requirements.txt
    """

    requirements_file = "requirements.txt"

    if not os.path.exists(requirements_file):
        return "❌ requirements.txt not found."

    with open(requirements_file, "r") as f:
        installed = [line.strip().lower() for line in f.readlines()]

    missing = []

    for lib in required_libraries:
        if lib.lower() not in installed:
            missing.append(lib)

    if not missing:
        return "✅ All required libraries are present in requirements.txt"

    return (
        "⚠️ Validation Result:\n"
        "Missing Libraries:\n"
        + "\n".join(f"- {lib}" for lib in missing)
    )