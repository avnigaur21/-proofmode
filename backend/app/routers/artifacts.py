from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from app.services.artifacts import artifact_path
from app.services.evidence_bundle import evidence_bundle_service
from app.services.run_service import run_service

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


@router.get("/bundles/{run_id}")
def evidence_bundle(run_id: str) -> FileResponse:
    run = run_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    artifact = evidence_bundle_service.export(run)
    path = Path(artifact["path"])
    return FileResponse(path=path, media_type="application/zip", filename=path.name)


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
