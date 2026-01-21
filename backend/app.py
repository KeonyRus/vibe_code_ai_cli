"""
FastAPI приложение - главный модуль
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from .database import init_db
from .config import load_settings, load_all_projects
from .routers import projects, terminal, settings, env_editor, zeusovich
from .workspace import sync_zeusovich_workspace


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle события приложения"""
    # Startup
    await init_db()
    print("[OK] Database initialized")

    # Sync Zeusovich workspace
    result = sync_zeusovich_workspace()
    print(f"[OK] Zeusovich workspace: {result['workspace_path']}")
    print(f"     Synced {len(result['synced'])} projects")
    if result['failed']:
        print(f"     [WARN] Failed to sync {len(result['failed'])} projects:")
        for f in result['failed']:
            print(f"       - {f['name']}: {f['error']}")

    print("[OK] Airganizator started on http://127.0.0.1:6680")
    yield
    # Shutdown
    from .process_manager import process_manager
    await process_manager.stop_all()
    print("[OK] All processes stopped")


app = FastAPI(
    title="Airganizator",
    description="LLM CLI Orchestrator",
    version="0.1.0",
    lifespan=lifespan
)

# Роутеры API
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(terminal.router, prefix="/api/terminal", tags=["terminal"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(env_editor.router, prefix="/api/env", tags=["env"])
app.include_router(zeusovich.router, prefix="/api/zeusovich", tags=["zeusovich"])

# Статические файлы
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def root():
    """Главная страница"""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/favicon.ico")
async def favicon():
    """Favicon"""
    favicon_path = Path(__file__).parent.parent / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    return Response(status_code=404)


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok", "service": "airganizator"}
