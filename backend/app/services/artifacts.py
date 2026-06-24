from pathlib import Path


def artifact_root() -> Path:
    current_file = Path(__file__).resolve()

    for parent in current_file.parents:
        if (parent / "proofmode-runs").exists() or (parent / "docker-compose.yml").exists():
            return parent / "proofmode-runs"

    return Path.cwd() / "proofmode-runs"


def artifact_url(*parts: str) -> str:
    clean_parts = [part.strip("/\\") for part in parts if part]
    return "/artifacts/" + "/".join(clean_parts)


def artifact_path(*parts: str) -> Path:
    root = artifact_root().resolve()
    candidate = root.joinpath(*parts).resolve()

    if root != candidate and root not in candidate.parents:
        raise ValueError("Artifact path escapes the artifact root.")

    return candidate
