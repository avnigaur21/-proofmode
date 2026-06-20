from pathlib import Path


def artifact_root() -> Path:
    current_file = Path(__file__).resolve()

    for parent in current_file.parents:
        if (parent / "proofmode-runs").exists() or (parent / "docker-compose.yml").exists():
            return parent / "proofmode-runs"

    return Path.cwd() / "proofmode-runs"

