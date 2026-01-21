"""
API роутер для глобальных настроек
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from ..config import (
    GlobalSettings, APIKeys, LLMType, WorkMode,
    load_settings, save_settings
)

router = APIRouter()


class SettingsUpdate(BaseModel):
    """Модель для обновления настроек"""
    base_projects_path: Optional[str] = None
    default_llm: Optional[LLMType] = None
    default_mode: Optional[WorkMode] = None


class APIKeysUpdate(BaseModel):
    """Модель для обновления API ключей"""
    anthropic: Optional[str] = None
    openai: Optional[str] = None
    google: Optional[str] = None


@router.get("/")
async def get_settings():
    """Получение текущих настроек"""
    settings = load_settings()
    # Маскируем API ключи
    result = settings.model_dump()
    if result["api_keys"]["anthropic"]:
        result["api_keys"]["anthropic"] = "***" + result["api_keys"]["anthropic"][-4:]
    if result["api_keys"]["openai"]:
        result["api_keys"]["openai"] = "***" + result["api_keys"]["openai"][-4:]
    if result["api_keys"]["google"]:
        result["api_keys"]["google"] = "***" + result["api_keys"]["google"][-4:]
    return result


@router.put("/")
async def update_settings(data: SettingsUpdate):
    """Обновление настроек"""
    settings = load_settings()

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(settings, key, value)

    save_settings(settings)
    return {"status": "ok"}


@router.put("/api-keys")
async def update_api_keys(data: APIKeysUpdate):
    """Обновление API ключей"""
    settings = load_settings()

    if data.anthropic is not None:
        settings.api_keys.anthropic = data.anthropic
    if data.openai is not None:
        settings.api_keys.openai = data.openai
    if data.google is not None:
        settings.api_keys.google = data.google

    save_settings(settings)
    return {"status": "ok"}


@router.get("/llm-types")
async def get_llm_types():
    """Получение списка доступных LLM"""
    return [{"value": t.value, "label": t.name} for t in LLMType]


@router.get("/work-modes")
async def get_work_modes():
    """Получение списка режимов работы"""
    return [{"value": m.value, "label": m.name} for m in WorkMode]
