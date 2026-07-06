from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import artifacts, claims, demo, projects, runs, settings

app = FastAPI(title="ProofMode API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(artifacts.router)
app.include_router(claims.router)
app.include_router(demo.router)
app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(settings.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
