# Airganizator

**LLM CLI Orchestrator** — веб-интерфейс для управления несколькими AI-ассистентами для кодинга.

Управляйте Claude Code, Codex, Gemini CLI и Aider из одного окна браузера.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Возможности

- **Мульти-проектность** — добавляйте неограниченное количество проектов
- **Разные LLM CLI** — Claude Code, Codex, Gemini CLI, Aider или кастомная команда
- **Полноценный терминал** — PTY с поддержкой цветов, интерактивных команд
- **Режимы работы** — Planning, Development, Bugfix с разными системными промптами
- **Консоль проекта** — отдельный PowerShell терминал для каждого проекта
- **Редактор .env** — редактируйте переменные окружения прямо из интерфейса
- **Git интеграция** — отображение ветки и ссылки на репозиторий
- **Zeusovich** — глобальный CLI с доступом ко всем проектам через junction links
- **Статус LLM** — индикация когда AI печатает или закончил ответ
- **Drag & Drop** — перетаскивание проектов для изменения порядка

## Скриншот

```
┌─────────────────────────────────────────────────────────────┐
│ ⚡ Airganizator                          [⚡] [⚙️] [+ Add]  │
├──────────────┬──────────────────────────────────────────────┤
│ Projects     │  my-project              ● Running           │
│ ┌──────────┐ │  ┌─────────────────────────────────────────┐ │
│ │ project1 │ │  │ 📋 Plan │ 💻 Dev │ 🐛 Fix │   ▶  ⏹    │ │
│ │ project2 │ │  ├─────────────────────────────────────────┤ │
│ │ project3 │ │  │ 💻 LLM │ ⌨️ Console                     │ │
│ └──────────┘ │  │                                         │ │
│              │  │ > claude                                │ │
│              │  │ ╭─────────────────────────────────────╮ │ │
│              │  │ │ How can I help you today?           │ │ │
│              │  │ ╰─────────────────────────────────────╯ │ │
└──────────────┴──────────────────────────────────────────────┘
```

## Установка

### Требования

- Python 3.10+
- Windows (для pywinpty)
- Установленные CLI: `claude`, `codex`, `gemini` или `aider`

### Шаги

```bash
# Клонируйте репозиторий
git clone https://github.com/KeonyRus/vibe_code_ai_cli.git
cd vibe_code_ai_cli

# Создайте виртуальное окружение
python -m venv venv
venv\Scripts\activate

# Установите зависимости
pip install -r requirements.txt

# Запустите
python main.py
```

Откройте в браузере: **http://127.0.0.1:6680**

## Структура проекта

```
airganizator/
├── backend/
│   ├── app.py              # FastAPI приложение
│   ├── config.py           # Конфигурация и модели
│   ├── database.py         # SQLite для истории
│   ├── process_manager.py  # Управление PTY процессами
│   ├── workspace.py        # Junction links для Zeusovich
│   └── routers/
│       ├── projects.py     # API проектов
│       ├── terminal.py     # WebSocket терминала
│       ├── settings.py     # Настройки
│       ├── env_editor.py   # Редактор .env
│       └── zeusovich.py    # Глобальный CLI
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── api.js          # API клиент
│       ├── app.js          # Основная логика
│       ├── terminal.js     # LLM терминал
│       ├── console.js      # Консоль проекта
│       └── zeusovich.js    # Zeusovich терминал
├── prompts/                # Системные промпты для режимов
├── main.py                 # Точка входа
└── requirements.txt
```

## Использование

### Добавление проекта

1. Нажмите **+ Add Project**
2. Укажите имя и путь к проекту
3. Выберите LLM CLI (Claude, Codex, Gemini, Aider)
4. Нажмите **Save**

### Работа с терминалом

- **▶ Start** — запустить LLM CLI
- **⏹ Stop** — остановить процесс
- Переключайтесь между **LLM** и **Console** табами
- Меняйте режим работы: **Plan**, **Dev**, **Fix**

### Zeusovich (глобальный CLI)

Нажмите **⚡** в хедере для открытия Zeusovich — Claude Code с доступом ко всем вашим проектам через junction links.

## Конфигурация

При первом запуске создаются папки:
- `config/` — настройки и проекты (YAML)
- `data/` — база данных истории (SQLite)
- `zeusovich-workspace/` — junction links на проекты

## Технологии

- **Backend**: FastAPI, WebSocket, pywinpty, aiosqlite
- **Frontend**: Vanilla JS, xterm.js
- **Storage**: YAML configs, SQLite history

## Лицензия

MIT License

## Автор

[@KeonyRus](https://github.com/KeonyRus)
