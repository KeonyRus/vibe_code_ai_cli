"""
Zeusovich Workspace Manager
Создаёт и управляет junction-ссылками на все проекты
"""
import os
import subprocess
from pathlib import Path
from typing import Optional

from .config import load_all_projects, CONFIG_DIR

# Папка workspace рядом с config
WORKSPACE_DIR = CONFIG_DIR.parent / "zeusovich-workspace"


def sync_zeusovich_workspace() -> dict:
    """
    Синхронизирует workspace с текущими проектами.
    Создаёт junction-ссылки на все папки проектов.

    Returns:
        dict: {
            "workspace_path": str,
            "synced": [{"name": ..., "path": ...}, ...],
            "failed": [{"name": ..., "path": ..., "error": ...}, ...]
        }
    """
    # Создаём папку workspace если нет
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    projects = load_all_projects()
    synced = []
    failed = []

    # Получаем текущие ссылки в workspace
    existing_links = set()
    if WORKSPACE_DIR.exists():
        for item in WORKSPACE_DIR.iterdir():
            existing_links.add(item.name)

    # Создаём ссылки для проектов
    project_names = set()
    for project in projects:
        project_path = Path(project.path)
        # Используем имя проекта как имя ссылки
        link_name = project.name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        project_names.add(link_name)
        link_path = WORKSPACE_DIR / link_name

        # Проверяем существует ли папка проекта
        if not project_path.exists():
            failed.append({
                "name": project.name,
                "path": str(project_path),
                "error": "Project folder does not exist"
            })
            continue

        # Если ссылка уже существует и указывает на правильную папку - пропускаем
        if link_path.exists():
            try:
                # Проверяем куда указывает ссылка
                if link_path.is_symlink() or link_path.is_junction():
                    real_path = os.path.realpath(link_path)
                    if Path(real_path) == project_path.resolve():
                        synced.append({
                            "name": project.name,
                            "path": str(project_path)
                        })
                        continue
                # Ссылка существует но указывает не туда - удаляем
                remove_junction(link_path)
            except Exception:
                pass

        # Создаём junction
        result = create_junction(link_path, project_path)
        if result["success"]:
            synced.append({
                "name": project.name,
                "path": str(project_path)
            })
        else:
            failed.append({
                "name": project.name,
                "path": str(project_path),
                "error": result["error"]
            })

    # Удаляем старые ссылки на несуществующие проекты
    for link_name in existing_links:
        if link_name not in project_names:
            try:
                link_path = WORKSPACE_DIR / link_name
                remove_junction(link_path)
            except Exception:
                pass

    return {
        "workspace_path": str(WORKSPACE_DIR),
        "synced": synced,
        "failed": failed
    }


def create_junction(link_path: Path, target_path: Path) -> dict:
    """Создаёт junction link (Windows) или symlink (Unix)"""
    try:
        if os.name == 'nt':
            # Windows: используем mklink /J для junction
            # Junction не требует прав администратора
            result = subprocess.run(
                ['cmd', '/c', 'mklink', '/J', str(link_path), str(target_path)],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr or "mklink failed"}
        else:
            # Unix: обычный symlink
            os.symlink(target_path, link_path)

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def remove_junction(link_path: Path) -> bool:
    """Удаляет junction link"""
    try:
        if os.name == 'nt':
            # На Windows junction удаляется как директория
            if link_path.is_dir():
                os.rmdir(link_path)
            else:
                os.remove(link_path)
        else:
            os.unlink(link_path)
        return True
    except Exception:
        return False


def get_workspace_path() -> str:
    """Возвращает путь к workspace"""
    return str(WORKSPACE_DIR)


# Расширение Path для проверки junction
def _is_junction(path: Path) -> bool:
    """Проверяет является ли путь junction point"""
    try:
        import ctypes
        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        return attrs != -1 and (attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    except Exception:
        return False

# Monkey-patch Path
Path.is_junction = lambda self: _is_junction(self)
