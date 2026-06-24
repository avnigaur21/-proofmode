from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from app.services.artifacts import artifact_path

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/screenshots/{filename}")
def screenshot(filename: str) -> FileResponse:
    return _file_response("screenshots", filename, media_type="image/png")


@router.get("/reports/{filename}")
def report(filename: str) -> PlainTextResponse:
    path = _safe_file("reports", filename)
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


@router.get("/snapshots/{snapshot_type}/{filename}")
def snapshot(snapshot_type: str, filename: str) -> FileResponse:
    if snapshot_type not in {"api", "db", "diff"}:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return _file_response("snapshots", snapshot_type, filename, media_type="application/json")


def _file_response(*parts: str, media_type: str) -> FileResponse:
    path = _safe_file(*parts)
    return FileResponse(path=path, media_type=media_type, filename=path.name)


def _safe_file(*parts: str) -> Path:
    if any(_is_unsafe_part(part) for part in parts):
        raise HTTPException(status_code=404, detail="Artifact not found")

    try:
        path = artifact_path(*parts)
    except ValueError:
        raise HTTPException(status_code=404, detail="Artifact not found") from None

    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    return path


def _is_unsafe_part(part: str) -> bool:
    return part in {"", ".", ".."} or "/" in part or "\\" in part
