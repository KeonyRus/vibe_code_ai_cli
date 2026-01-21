"""
API роутер для редактирования .env файлов проектов
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from typing import Optional

from ..config import load_project

router = APIRouter()


class EnvUpdate(BaseModel):
    """Модель для обновления .env"""
    content: str


class EnvVarUpdate(BaseModel):
    """Модель для обновления отдельной переменной"""
    key: str
    value: str


def parse_env_file(content: str) -> dict[str, str]:
    """Парсинг .env файла в словарь"""
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            # Убираем кавычки если есть
            value = value.strip()
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            result[key.strip()] = value
    return result


def dict_to_env(data: dict[str, str]) -> str:
    """Конвертация словаря обратно в .env формат"""
    lines = []
    for key, value in data.items():
        # Добавляем кавычки если есть пробелы
        if " " in value or '"' in value:
            value = f'"{value}"'
        lines.append(f"{key}={value}")
    return "\n".join(lines)


@router.get("/{project_id}")
async def get_env(project_id: str):
    """Получение содержимого .env файла проекта"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    env_path = Path(project.path) / project.env_file
    if not env_path.exists():
        return {"exists": False, "content": "", "variables": {}}

    content = env_path.read_text(encoding="utf-8")
    variables = parse_env_file(content)

    # Маскируем значения с ключевыми словами
    masked_vars = {}
    sensitive_keywords = ["key", "secret", "password", "token", "credential"]
    for key, value in variables.items():
        if any(kw in key.lower() for kw in sensitive_keywords) and value:
            masked_vars[key] = "***" + value[-4:] if len(value) > 4 else "****"
        else:
            masked_vars[key] = value

    return {
        "exists": True,
        "content": content,
        "variables": masked_vars,
        "path": str(env_path)
    }


@router.put("/{project_id}")
async def update_env(project_id: str, data: EnvUpdate):
    """Обновление всего .env файла"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    env_path = Path(project.path) / project.env_file

    # Создаем директорию если не существует
    env_path.parent.mkdir(parents=True, exist_ok=True)

    env_path.write_text(data.content, encoding="utf-8")
    return {"status": "ok", "path": str(env_path)}


@router.put("/{project_id}/var")
async def update_env_var(project_id: str, data: EnvVarUpdate):
    """Обновление отдельной переменной в .env"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    env_path = Path(project.path) / project.env_file

    # Читаем существующий файл или создаем пустой
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        variables = parse_env_file(content)
    else:
        variables = {}

    # Обновляем переменную
    variables[data.key] = data.value

    # Записываем обратно
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(dict_to_env(variables), encoding="utf-8")

    return {"status": "ok", "key": data.key}


@router.delete("/{project_id}/var/{key}")
async def delete_env_var(project_id: str, key: str):
    """Удаление переменной из .env"""
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    env_path = Path(project.path) / project.env_file
    if not env_path.exists():
        raise HTTPException(status_code=404, detail=".env file not found")

    content = env_path.read_text(encoding="utf-8")
    variables = parse_env_file(content)

    if key not in variables:
        raise HTTPException(status_code=404, detail="Variable not found")

    del variables[key]
    env_path.write_text(dict_to_env(variables), encoding="utf-8")

    return {"status": "ok", "key": key}
