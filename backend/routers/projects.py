"""
API роутер для управления проектами
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import uuid
import re

from ..config import (
    ProjectConfig, WorkMode, LLMType,
    load_all_projects, load_project, save_project, delete_project
)
from ..process_manager import process_manager
from ..workspace import sync_zeusovich_workspace


def get_git_info(project_path: str) -> dict:
    """Извлекает информацию о git репозитории из проекта"""
    path = Path(project_path)
    git_dir = path / ".git"

    result = {
        "has_git": False,
        "remote_url": None,
        "remote_name": None,
        "web_url": None,
        "branch": None
    }

    if not git_dir.exists():
        return result

    result["has_git"] = True

    # Читаем текущую ветку
    head_file = git_dir / "HEAD"
    if head_file.exists():
        try:
            content = head_file.read_text().strip()
            if content.startswith("ref: refs/heads/"):
                result["branch"] = content.replace("ref: refs/heads/", "")
        except:
            pass

    # Читаем remote URL из config
    config_file = git_dir / "config"
    if config_file.exists():
        try:
            content = config_file.read_text()
            # Ищем секцию [remote "origin"]
            remote_match = re.search(
                r'\[remote\s+"(\w+)"\]\s*\n\s*url\s*=\s*(.+)',
                content
            )
            if remote_match:
                result["remote_name"] = remote_match.group(1)
                remote_url = remote_match.group(2).strip()
                result["remote_url"] = remote_url

                # Конвертируем в web URL
                result["web_url"] = convert_to_web_url(remote_url)
        except:
            pass

    return result


def convert_to_web_url(git_url: str) -> Optional[str]:
    """Конвертирует git URL в web URL"""
    if not git_url:
        return None

    # SSH формат: git@github.com:user/repo.git
    ssh_match = re.match(r'git@([^:]+):(.+?)(?:\.git)?$', git_url)
    if ssh_match:
        host = ssh_match.group(1)
        path = ssh_match.group(2)
        return f"https://{host}/{path}"

    # HTTPS формат: https://github.com/user/repo.git
    https_match = re.match(r'https?://([^/]+)/(.+?)(?:\.git)?$', git_url)
    if https_match:
        host = https_match.group(1)
        path = https_match.group(2)
        return f"https://{host}/{path}"

    # Git протокол: git://github.com/user/repo.git
    git_match = re.match(r'git://([^/]+)/(.+?)(?:\.git)?$', git_url)
    if git_match:
        host = git_match.group(1)
        path = git_match.group(2)
        return f"https://{host}/{path}"

    return git_url

router = APIRouter()


class ProjectCreate(BaseModel):
    """Модель для создания проекта"""
    name: str
    path: str
    llm: LLMType = LLMType.CLAUDE_CODE
    llm_command: Optional[str] = None
    mode: WorkMode = WorkMode.DEVELOPMENT
    use_global_api_key: bool = True


class ProjectUpdate(BaseModel):
    """Модель для обновления проекта"""
    name: Optional[str] = None
    path: Optional[str] = None
    llm: Optional[LLMType] = None
    llm_command: Optional[str] = None
    mode: Optional[WorkMode] = None
    custom_prompt: Optional[str] = None
    use_global_api_key: Optional[bool] = None
    api_key: Optional[str] = None


class ModeChange(BaseModel):
    """Модель для смены режима"""
    mode: WorkMode


@router.get("/")
async def list_projects():
    """Получение списка всех проектов"""
    projects = load_all_projects()
    result = []
    for p in projects:
        result.append({
            **p.model_dump(),
            "running": process_manager.is_running(p.id),
            "git": get_git_info(p.path)
        })
    return result


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Получение проекта по ID"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {
        **project.model_dump(),
        "running": process_manager.is_running(project_id),
        "git": get_git_info(project.path)
    }


@router.post("/")
async def create_project(data: ProjectCreate):
    """Создание нового проекта"""
    project_id = str(uuid.uuid4())[:8]

    project = ProjectConfig(
        id=project_id,
        name=data.name,
        path=data.path,
        llm=data.llm,
        llm_command=data.llm_command,
        mode=data.mode,
        use_global_api_key=data.use_global_api_key
    )

    save_project(project)

    # Sync Zeusovich workspace to include new project
    sync_zeusovich_workspace()

    return project.model_dump()


@router.put("/{project_id}")
async def update_project(project_id: str, data: ProjectUpdate):
    """Обновление проекта"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Обновляем только переданные поля
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(project, key, value)

    save_project(project)
    return project.model_dump()


@router.delete("/{project_id}")
async def remove_project(project_id: str):
    """Удаление проекта"""
    # Останавливаем процесс если запущен
    if process_manager.is_running(project_id):
        await process_manager.stop_process(project_id)

    if not delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    # Sync Zeusovich workspace to remove old link
    sync_zeusovich_workspace()

    return {"status": "deleted", "id": project_id}


@router.post("/{project_id}/mode")
async def change_mode(project_id: str, data: ModeChange):
    """Смена режима работы проекта"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.mode = data.mode
    save_project(project)

    return {"status": "ok", "mode": data.mode.value}


@router.post("/{project_id}/start")
async def start_project(project_id: str):
    """Запуск процесса проекта"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if process_manager.is_running(project_id):
        raise HTTPException(status_code=400, detail="Process already running")

    session = await process_manager.start_process(project)
    return {
        "status": "started",
        "session_id": session.session_id,
        "project_id": project_id
    }


@router.post("/{project_id}/stop")
async def stop_project(project_id: str):
    """Остановка процесса проекта"""
    if not process_manager.is_running(project_id):
        raise HTTPException(status_code=400, detail="Process not running")

    await process_manager.stop_process(project_id)
    return {"status": "stopped", "project_id": project_id}


@router.post("/{project_id}/restart")
async def restart_project(project_id: str):
    """Перезапуск процесса проекта"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if process_manager.is_running(project_id):
        await process_manager.stop_process(project_id)

    session = await process_manager.start_process(project)
    return {
        "status": "restarted",
        "session_id": session.session_id,
        "project_id": project_id
    }


@router.get("/running/list")
async def list_running():
    """Получение списка запущенных проектов"""
    return {"running": process_manager.get_all_running()}


@router.post("/{project_id}/open-folder")
async def open_project_folder(project_id: str):
    """Открыть папку проекта в Explorer"""
    import subprocess

    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    path = Path(project.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Folder not found")

    # Open in Windows Explorer
    subprocess.Popen(f'explorer "{path}"', shell=True)

    return {"status": "ok", "path": str(path)}
