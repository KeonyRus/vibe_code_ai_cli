# Airganizator

**LLM CLI Orchestrator** — web interface for managing multiple AI coding assistants.

## Why?

If you work with multiple projects using AI assistants (Claude Code, Codex, Gemini CLI), you know the pain:
- **Too many terminals** — one for each project, easy to get lost
- **Constant switching** — alt+tab between windows kills focus and flow
- **No overview** — can't see which AI is working and which is waiting for input

**Airganizator fixes this:**

| Problem | Solution |
|---------|----------|
| Too many terminals | All projects in one browser window |
| Can't see AI status | Visual indicators: AI typing or idle (card highlighting) |
| Different CLI tools | Unified interface for Claude, Codex, Gemini, Aider |
| Context switching | One click — you're in another project |
| AI can't see other projects | Zeusovich — global CLI with access to all projects |

**Key benefits:**
- See all projects and their statuses at once
- Instant switching between projects
- Know when AI finished responding (even if you're in another project)
- One tool instead of a dozen terminals

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Multi-project** — add unlimited projects
- **Multiple LLM CLIs** — Claude Code, Codex, Gemini CLI, Aider or custom command
- **Full terminal** — PTY with colors, interactive commands support
- **Work modes** — Planning, Development, Bugfix with different system prompts
- **Project console** — separate PowerShell terminal for each project
- **.env editor** — edit environment variables right from the interface
- **Git integration** — branch display and repository links
- **Zeusovich** — global CLI with access to all projects via junction links
- **LLM status** — indicators when AI is typing or finished responding
- **Drag & Drop** — reorder projects by dragging

## Screenshot

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

## Installation

### Requirements

- Python 3.10+
- Windows (for pywinpty)
- Installed CLIs: `claude`, `codex`, `gemini` or `aider`

### Steps

```bash
# Clone the repository
git clone https://github.com/KeonyRus/vibe_code_ai_cli.git
cd vibe_code_ai_cli

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

Open in browser: **http://127.0.0.1:6680**

## Project Structure

```
airganizator/
├── backend/
│   ├── app.py              # FastAPI application
│   ├── config.py           # Configuration and models
│   ├── database.py         # SQLite for history
│   ├── process_manager.py  # PTY process management
│   ├── workspace.py        # Junction links for Zeusovich
│   └── routers/
│       ├── projects.py     # Projects API
│       ├── terminal.py     # Terminal WebSocket
│       ├── settings.py     # Settings
│       ├── env_editor.py   # .env editor
│       └── zeusovich.py    # Global CLI
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── api.js          # API client
│       ├── app.js          # Main logic
│       ├── terminal.js     # LLM terminal
│       ├── console.js      # Project console
│       └── zeusovich.js    # Zeusovich terminal
├── prompts/                # System prompts for modes
├── main.py                 # Entry point
└── requirements.txt
```

## Usage

### Adding a project

1. Click **+ Add Project**
2. Enter name and path to the project
3. Select LLM CLI (Claude, Codex, Gemini, Aider)
4. Click **Save**

### Working with terminal

- **▶ Start** — launch LLM CLI
- **⏹ Stop** — stop the process
- Switch between **LLM** and **Console** tabs
- Change work mode: **Plan**, **Dev**, **Fix**

### Zeusovich (global CLI)

Click **⚡** in the header to open Zeusovich — Claude Code with access to all your projects via junction links.

## Configuration

On first launch, these folders are created:
- `config/` — settings and projects (YAML)
- `data/` — history database (SQLite)
- `zeusovich-workspace/` — junction links to projects

## Tech Stack

- **Backend**: FastAPI, WebSocket, pywinpty, aiosqlite
- **Frontend**: Vanilla JS, xterm.js
- **Storage**: YAML configs, SQLite history

## License

MIT License

## Author

[@KeonyRus](https://github.com/KeonyRus)
