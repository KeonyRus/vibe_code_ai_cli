"""
SQLite база данных для хранения истории сессий
"""
import aiosqlite
from pathlib import Path
from datetime import datetime
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "history.db"


async def init_db():
    """Инициализация базы данных"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                mode TEXT,
                llm_type TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                role TEXT NOT NULL,  -- 'user', 'assistant', 'system'
                content TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS terminal_output (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                output TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        await db.commit()


async def create_session(project_id: str, mode: str, llm_type: str) -> int:
    """Создание новой сессии"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO sessions (project_id, mode, llm_type) VALUES (?, ?, ?)",
            (project_id, mode, llm_type)
        )
        await db.commit()
        return cursor.lastrowid


async def end_session(session_id: int):
    """Завершение сессии"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id)
        )
        await db.commit()


async def add_message(session_id: int, role: str, content: str):
    """Добавление сообщения в историю"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        await db.commit()


async def add_terminal_output(session_id: int, output: str):
    """Сохранение вывода терминала"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO terminal_output (session_id, output) VALUES (?, ?)",
            (session_id, output)
        )
        await db.commit()


async def get_session_history(session_id: int) -> list[dict]:
    """Получение истории сессии"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_project_sessions(project_id: str, limit: int = 10) -> list[dict]:
    """Получение последних сессий проекта"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM sessions
               WHERE project_id = ?
               ORDER BY started_at DESC
               LIMIT ?""",
            (project_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_sessions(limit: int = 50) -> list[dict]:
    """Получение всех последних сессий"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM sessions
               ORDER BY started_at DESC
               LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_recent_terminal_output(project_id: str = None, limit: int = 100) -> list[dict]:
    """Получение последнего вывода терминала"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if project_id:
            cursor = await db.execute(
                """SELECT t.*, s.project_id FROM terminal_output t
                   JOIN sessions s ON t.session_id = s.id
                   WHERE s.project_id = ?
                   ORDER BY t.timestamp DESC
                   LIMIT ?""",
                (project_id, limit)
            )
        else:
            cursor = await db.execute(
                """SELECT t.*, s.project_id FROM terminal_output t
                   JOIN sessions s ON t.session_id = s.id
                   ORDER BY t.timestamp DESC
                   LIMIT ?""",
                (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def search_messages(query: str, limit: int = 50) -> list[dict]:
    """Поиск по сообщениям"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT m.*, s.project_id FROM messages m
               JOIN sessions s ON m.session_id = s.id
               WHERE m.content LIKE ?
               ORDER BY m.timestamp DESC
               LIMIT ?""",
            (f"%{query}%", limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_stats() -> dict:
    """Получение статистики"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Всего сессий
        cursor = await db.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = (await cursor.fetchone())[0]

        # Всего сообщений
        cursor = await db.execute("SELECT COUNT(*) FROM messages")
        total_messages = (await cursor.fetchone())[0]

        # Сессий по проектам
        cursor = await db.execute(
            """SELECT project_id, COUNT(*) as count
               FROM sessions GROUP BY project_id"""
        )
        sessions_by_project = {row[0]: row[1] for row in await cursor.fetchall()}

        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "sessions_by_project": sessions_by_project
        }
