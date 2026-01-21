"""
Pydantic модели для конфигурации
"""
from enum import Enum
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field


class WorkMode(str, Enum):
    PLANNING = "planning"
    DEVELOPMENT = "development"
    BUGFIX = "bugfix"


class LLMType(str, Enum):
    CLAUDE_CODE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"
    AIDER = "aider"
    CUSTOM = "custom"


class ProjectConfig(BaseModel):
    """Конфигурация отдельного проекта"""
    id: str
    name: str
    path: str
    llm: LLMType = LLMType.CLAUDE_CODE
    llm_command: Optional[str] = None  # Кастомная команда если llm=custom
    mode: WorkMode = WorkMode.DEVELOPMENT
    custom_prompt: Optional[str] = None  # Путь к файлу с кастомным промптом
    env_file: str = ".env"
    use_global_api_key: bool = True
    api_key: Optional[str] = None  # Используется если use_global_api_key=False

    def get_llm_command(self) -> str:
        """Возвращает команду для запуска LLM CLI"""
        if self.llm_command:
            return self.llm_command
        return self.llm.value


class APIKeys(BaseModel):
    """API ключи для разных LLM"""
    anthropic: Optional[str] = None
    openai: Optional[str] = None
    google: Optional[str] = None


class GlobalSettings(BaseModel):
    """Глобальные настройки приложения"""
    base_projects_path: str = "D:/projects"
    default_llm: LLMType = LLMType.CLAUDE_CODE
    default_mode: WorkMode = WorkMode.DEVELOPMENT
    api_keys: APIKeys = Field(default_factory=APIKeys)


class AppConfig(BaseModel):
    """Полная конфигурация приложения"""
    settings: GlobalSettings = Field(default_factory=GlobalSettings)
    projects: list[ProjectConfig] = Field(default_factory=list)


# Пути к конфигам
CONFIG_DIR = Path(__file__).parent.parent / "config"
SETTINGS_FILE = CONFIG_DIR / "settings.yaml"
PROJECTS_DIR = CONFIG_DIR / "projects"


def load_settings() -> GlobalSettings:
    """Загрузка глобальных настроек"""
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return GlobalSettings(**data)
    return GlobalSettings()


def save_settings(settings: GlobalSettings) -> None:
    """Сохранение глобальных настроек"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(settings.model_dump(mode='json'), f, default_flow_style=False, allow_unicode=True)


def load_project(project_id: str) -> Optional[ProjectConfig]:
    """Загрузка конфига проекта"""
    project_file = PROJECTS_DIR / f"{project_id}.yaml"
    if project_file.exists():
        with open(project_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return ProjectConfig(**data)
    return None


def save_project(project: ProjectConfig) -> None:
    """Сохранение конфига проекта"""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    project_file = PROJECTS_DIR / f"{project.id}.yaml"
    with open(project_file, "w", encoding="utf-8") as f:
        yaml.dump(project.model_dump(mode='json'), f, default_flow_style=False, allow_unicode=True)


def delete_project(project_id: str) -> bool:
    """Удаление конфига проекта"""
    project_file = PROJECTS_DIR / f"{project_id}.yaml"
    if project_file.exists():
        project_file.unlink()
        return True
    return False


def load_all_projects() -> list[ProjectConfig]:
    """Загрузка всех проектов"""
    projects = []
    if PROJECTS_DIR.exists():
        for file in PROJECTS_DIR.glob("*.yaml"):
            with open(file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                try:
                    projects.append(ProjectConfig(**data))
                except Exception:
                    pass  # Пропускаем невалидные конфиги
    return projects
