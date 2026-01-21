"""
Process Manager - управление PTY процессами CLI LLM
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable
import winpty

from .config import ProjectConfig, WorkMode
from .database import create_session, end_session, add_terminal_output


@dataclass
class ProcessSession:
    """Активная сессия процесса"""
    project_id: str
    process: winpty.PTY
    session_id: int
    mode: WorkMode
    running: bool = True
    output_callbacks: list[Callable[[str], Awaitable[None]]] = field(default_factory=list)
    status_callbacks: list[Callable[[str], Awaitable[None]]] = field(default_factory=list)
    output_history: str = ""  # Буфер истории вывода
    last_output_time: float = 0  # Время последнего вывода
    is_typing: bool = False  # LLM печатает
    _read_task: Optional[asyncio.Task] = None
    _idle_task: Optional[asyncio.Task] = None
    MAX_HISTORY_SIZE: int = 50000  # ~50KB истории
    IDLE_TIMEOUT: float = 2.0  # Секунд без вывода = idle


@dataclass
class ConsoleSession:
    """Сессия консоли (обычный шелл)"""
    project_id: str
    process: winpty.PTY
    running: bool = True
    output_callbacks: list[Callable[[str], Awaitable[None]]] = field(default_factory=list)
    output_history: str = ""
    _read_task: Optional[asyncio.Task] = None
    MAX_HISTORY_SIZE: int = 50000


@dataclass
class ZeusovichSession:
    """Сессия Zeusovich - глобальный CLI с доступом ко всем проектам"""
    process: winpty.PTY
    running: bool = True
    output_callbacks: list[Callable[[str], Awaitable[None]]] = field(default_factory=list)
    output_history: str = ""
    _read_task: Optional[asyncio.Task] = None
    MAX_HISTORY_SIZE: int = 100000  # Больше истории для Zeusovich
    started_project_ids: set[str] = field(default_factory=set)  # ID проектов при запуске


class ProcessManager:
    """Менеджер процессов для всех проектов"""

    def __init__(self):
        self.sessions: dict[str, ProcessSession] = {}
        self.console_sessions: dict[str, ConsoleSession] = {}
        self.zeusovich_session: Optional[ZeusovichSession] = None
        self.pending_callbacks: dict[str, list[Callable[[str], Awaitable[None]]]] = {}
        self.pending_console_callbacks: dict[str, list[Callable[[str], Awaitable[None]]]] = {}
        self.pending_zeusovich_callbacks: list[Callable[[str], Awaitable[None]]] = []
        self._lock = asyncio.Lock()

    def _build_command(self, project: ProjectConfig) -> str:
        """Построение команды запуска LLM CLI"""
        cmd = project.get_llm_command()
        # Просто запускаем CLI в директории проекта
        return f'cmd.exe /k "cd /d {project.path} && {cmd}"'

    async def start_process(self, project: ProjectConfig) -> ProcessSession:
        """Запуск нового процесса для проекта"""
        async with self._lock:
            # Останавливаем существующий процесс если есть
            if project.id in self.sessions:
                await self._stop_session(project.id)

            # Создаем сессию в БД
            session_id = await create_session(
                project.id,
                project.mode.value,
                project.llm.value
            )

            # Создаем PTY и запускаем CLI
            cmd = self._build_command(project)
            print(f"[DEBUG] Command: {cmd}")

            pty = winpty.PTY(120, 30)
            print(f"[DEBUG] PTY created, spawning...")
            pty.spawn(cmd)
            print(f"[DEBUG] Process spawned!")

            session = ProcessSession(
                project_id=project.id,
                process=pty,
                session_id=session_id,
                mode=project.mode
            )

            # Добавляем pending callbacks
            if project.id in self.pending_callbacks:
                session.output_callbacks.extend(self.pending_callbacks[project.id])
                print(f"[DEBUG] Added {len(self.pending_callbacks[project.id])} pending callbacks")

            self.sessions[project.id] = session

            # Запускаем асинхронное чтение вывода
            session._read_task = asyncio.create_task(
                self._read_output(session)
            )

            return session

    async def _notify_status(self, session: ProcessSession, status: str):
        """Уведомление о смене статуса (typing/idle)"""
        for callback in session.status_callbacks:
            try:
                await callback(status)
            except Exception:
                pass

    async def _read_output(self, session: ProcessSession):
        """Асинхронное чтение вывода из PTY"""
        buffer = ""
        read_count = 0
        while session.running:
            try:
                # Читаем данные из PTY
                data = session.process.read(blocking=False)
                if data:
                    read_count += 1
                    buffer += data
                    session.last_output_time = time.time()

                    # Отмечаем что LLM печатает
                    if not session.is_typing:
                        session.is_typing = True
                        await self._notify_status(session, "typing")

                    # Сохраняем в историю сессии
                    session.output_history += data
                    if len(session.output_history) > session.MAX_HISTORY_SIZE:
                        session.output_history = session.output_history[-session.MAX_HISTORY_SIZE:]

                    # Сохраняем в БД (батчим)
                    if len(buffer) > 512:
                        await add_terminal_output(session.session_id, buffer)
                        buffer = ""

                    # Отправляем всем подписчикам
                    for callback in session.output_callbacks:
                        try:
                            await callback(data)
                        except Exception:
                            pass
                else:
                    # Проверяем idle состояние
                    if session.is_typing and session.last_output_time > 0:
                        if time.time() - session.last_output_time > session.IDLE_TIMEOUT:
                            session.is_typing = False
                            await self._notify_status(session, "idle")
                    await asyncio.sleep(0.05)  # 50ms пауза если нет данных
            except Exception as e:
                if session.running:
                    print(f"Error reading from PTY: {e}")
                break

        # Сохраняем остаток буфера
        if buffer:
            await add_terminal_output(session.session_id, buffer)

    async def write_to_process(self, project_id: str, data: str) -> bool:
        """Отправка данных в процесс"""
        session = self.sessions.get(project_id)
        if session and session.running:
            try:
                session.process.write(data)
                return True
            except Exception as e:
                print(f"Error writing to PTY: {e}")
        return False

    async def resize_terminal(self, project_id: str, cols: int, rows: int) -> bool:
        """Изменение размера терминала"""
        session = self.sessions.get(project_id)
        if session and session.running:
            try:
                session.process.set_size(cols, rows)
                return True
            except Exception:
                pass
        return False

    def add_output_callback(
        self,
        project_id: str,
        callback: Callable[[str], Awaitable[None]]
    ):
        """Добавление callback для получения вывода"""
        session = self.sessions.get(project_id)
        if session:
            session.output_callbacks.append(callback)
        else:
            # Сохраняем в pending если session ещё нет
            if project_id not in self.pending_callbacks:
                self.pending_callbacks[project_id] = []
            self.pending_callbacks[project_id].append(callback)

    def remove_output_callback(
        self,
        project_id: str,
        callback: Callable[[str], Awaitable[None]]
    ):
        """Удаление callback"""
        session = self.sessions.get(project_id)
        if session and callback in session.output_callbacks:
            session.output_callbacks.remove(callback)
        # Также удаляем из pending
        if project_id in self.pending_callbacks and callback in self.pending_callbacks[project_id]:
            self.pending_callbacks[project_id].remove(callback)

    def add_status_callback(
        self,
        project_id: str,
        callback: Callable[[str], Awaitable[None]]
    ):
        """Добавление callback для статуса (typing/idle)"""
        session = self.sessions.get(project_id)
        if session:
            session.status_callbacks.append(callback)

    def remove_status_callback(
        self,
        project_id: str,
        callback: Callable[[str], Awaitable[None]]
    ):
        """Удаление status callback"""
        session = self.sessions.get(project_id)
        if session and callback in session.status_callbacks:
            session.status_callbacks.remove(callback)

    async def _stop_session(self, project_id: str):
        """Остановка сессии (внутренний метод)"""
        session = self.sessions.get(project_id)
        if session:
            session.running = False

            # Отменяем задачу чтения
            if session._read_task:
                session._read_task.cancel()
                try:
                    await session._read_task
                except asyncio.CancelledError:
                    pass

            # Завершаем PTY
            try:
                session.process.close()
            except Exception:
                pass

            # Завершаем сессию в БД
            await end_session(session.session_id)

            del self.sessions[project_id]

    async def stop_process(self, project_id: str) -> bool:
        """Остановка процесса проекта"""
        async with self._lock:
            if project_id in self.sessions:
                await self._stop_session(project_id)
                return True
            return False

    async def stop_all(self):
        """Остановка всех процессов"""
        async with self._lock:
            for project_id in list(self.sessions.keys()):
                await self._stop_session(project_id)

    def get_session(self, project_id: str) -> Optional[ProcessSession]:
        """Получение сессии по ID проекта"""
        return self.sessions.get(project_id)

    def get_output_history(self, project_id: str) -> str:
        """Получение истории вывода"""
        session = self.sessions.get(project_id)
        if session:
            return session.output_history
        return ""

    def is_running(self, project_id: str) -> bool:
        """Проверка запущен ли процесс"""
        session = self.sessions.get(project_id)
        return session is not None and session.running

    def get_all_running(self) -> list[str]:
        """Получение списка запущенных проектов"""
        return [
            pid for pid, session in self.sessions.items()
            if session.running
        ]

    # ==================== CONSOLE METHODS ====================

    async def start_console(self, project_id: str, project_path: str) -> ConsoleSession:
        """Запуск консоли для проекта"""
        async with self._lock:
            # Останавливаем существующую консоль если есть
            if project_id in self.console_sessions:
                await self._stop_console_session(project_id)

            # Создаем PTY с PowerShell
            cmd = f'powershell.exe -NoLogo -NoExit -Command "cd \'{project_path}\'"'
            print(f"[DEBUG] Console command: {cmd}")

            pty = winpty.PTY(120, 30)
            pty.spawn(cmd)

            session = ConsoleSession(
                project_id=project_id,
                process=pty
            )

            # Добавляем pending callbacks
            if project_id in self.pending_console_callbacks:
                session.output_callbacks.extend(self.pending_console_callbacks[project_id])
                del self.pending_console_callbacks[project_id]

            self.console_sessions[project_id] = session

            # Запускаем чтение вывода
            session._read_task = asyncio.create_task(
                self._read_console_output(session)
            )

            return session

    async def _read_console_output(self, session: ConsoleSession):
        """Чтение вывода консоли"""
        while session.running:
            try:
                data = session.process.read(blocking=False)
                if data:
                    # Сохраняем в историю
                    session.output_history += data
                    if len(session.output_history) > session.MAX_HISTORY_SIZE:
                        session.output_history = session.output_history[-session.MAX_HISTORY_SIZE:]

                    # Отправляем подписчикам
                    for callback in session.output_callbacks:
                        try:
                            await callback(data)
                        except Exception:
                            pass
                else:
                    await asyncio.sleep(0.05)
            except Exception as e:
                if session.running:
                    print(f"Error reading console: {e}")
                break

    async def write_to_console(self, project_id: str, data: str) -> bool:
        """Отправка данных в консоль"""
        session = self.console_sessions.get(project_id)
        if session and session.running:
            try:
                session.process.write(data)
                return True
            except Exception as e:
                print(f"Error writing to console: {e}")
        return False

    async def resize_console(self, project_id: str, cols: int, rows: int) -> bool:
        """Изменение размера консоли"""
        session = self.console_sessions.get(project_id)
        if session and session.running:
            try:
                session.process.set_size(cols, rows)
                return True
            except Exception:
                pass
        return False

    def add_console_callback(
        self,
        project_id: str,
        callback: Callable[[str], Awaitable[None]]
    ):
        """Добавление callback для консоли"""
        session = self.console_sessions.get(project_id)
        if session:
            session.output_callbacks.append(callback)
        else:
            if project_id not in self.pending_console_callbacks:
                self.pending_console_callbacks[project_id] = []
            self.pending_console_callbacks[project_id].append(callback)

    def remove_console_callback(
        self,
        project_id: str,
        callback: Callable[[str], Awaitable[None]]
    ):
        """Удаление callback консоли"""
        session = self.console_sessions.get(project_id)
        if session and callback in session.output_callbacks:
            session.output_callbacks.remove(callback)
        if project_id in self.pending_console_callbacks and callback in self.pending_console_callbacks[project_id]:
            self.pending_console_callbacks[project_id].remove(callback)

    async def _stop_console_session(self, project_id: str):
        """Остановка консольной сессии"""
        session = self.console_sessions.get(project_id)
        if session:
            session.running = False
            if session._read_task:
                session._read_task.cancel()
                try:
                    await session._read_task
                except asyncio.CancelledError:
                    pass
            try:
                session.process.close()
            except Exception:
                pass
            del self.console_sessions[project_id]

    async def stop_console(self, project_id: str) -> bool:
        """Остановка консоли проекта"""
        async with self._lock:
            if project_id in self.console_sessions:
                await self._stop_console_session(project_id)
                return True
            return False

    def is_console_running(self, project_id: str) -> bool:
        """Проверка запущена ли консоль"""
        session = self.console_sessions.get(project_id)
        return session is not None and session.running

    def get_console_history(self, project_id: str) -> str:
        """Получение истории консоли"""
        session = self.console_sessions.get(project_id)
        if session:
            return session.output_history
        return ""

    # ==================== ZEUSOVICH METHODS ====================

    async def start_zeusovich(self, base_path: str, project_ids: set[str] = None) -> ZeusovichSession:
        """Запуск Zeusovich CLI в директории с проектами"""
        async with self._lock:
            # Останавливаем существующую сессию
            if self.zeusovich_session:
                await self._stop_zeusovich_session()

            # Запускаем Claude CLI в base_path
            cmd = f'cmd.exe /k "cd /d {base_path} && claude"'
            print(f"[DEBUG] Zeusovich command: {cmd}")

            pty = winpty.PTY(120, 30)
            pty.spawn(cmd)

            session = ZeusovichSession(
                process=pty,
                started_project_ids=project_ids or set()
            )

            # Добавляем pending callbacks
            if self.pending_zeusovich_callbacks:
                session.output_callbacks.extend(self.pending_zeusovich_callbacks)
                self.pending_zeusovich_callbacks = []

            self.zeusovich_session = session

            # Запускаем чтение вывода
            session._read_task = asyncio.create_task(
                self._read_zeusovich_output(session)
            )

            return session

    async def _read_zeusovich_output(self, session: ZeusovichSession):
        """Чтение вывода Zeusovich"""
        while session.running:
            try:
                data = session.process.read(blocking=False)
                if data:
                    # Сохраняем в историю
                    session.output_history += data
                    if len(session.output_history) > session.MAX_HISTORY_SIZE:
                        session.output_history = session.output_history[-session.MAX_HISTORY_SIZE:]

                    # Отправляем подписчикам
                    for callback in session.output_callbacks:
                        try:
                            await callback(data)
                        except Exception:
                            pass
                else:
                    await asyncio.sleep(0.05)
            except Exception as e:
                if session.running:
                    print(f"Error reading Zeusovich: {e}")
                break

    async def write_to_zeusovich(self, data: str) -> bool:
        """Отправка данных в Zeusovich"""
        if self.zeusovich_session and self.zeusovich_session.running:
            try:
                self.zeusovich_session.process.write(data)
                return True
            except Exception as e:
                print(f"Error writing to Zeusovich: {e}")
        return False

    async def resize_zeusovich(self, cols: int, rows: int) -> bool:
        """Изменение размера терминала Zeusovich"""
        if self.zeusovich_session and self.zeusovich_session.running:
            try:
                self.zeusovich_session.process.set_size(cols, rows)
                return True
            except Exception:
                pass
        return False

    def add_zeusovich_callback(self, callback: Callable[[str], Awaitable[None]]):
        """Добавление callback для Zeusovich"""
        if self.zeusovich_session:
            self.zeusovich_session.output_callbacks.append(callback)
        else:
            self.pending_zeusovich_callbacks.append(callback)

    def remove_zeusovich_callback(self, callback: Callable[[str], Awaitable[None]]):
        """Удаление callback Zeusovich"""
        if self.zeusovich_session and callback in self.zeusovich_session.output_callbacks:
            self.zeusovich_session.output_callbacks.remove(callback)
        if callback in self.pending_zeusovich_callbacks:
            self.pending_zeusovich_callbacks.remove(callback)

    async def _stop_zeusovich_session(self):
        """Остановка сессии Zeusovich"""
        if self.zeusovich_session:
            self.zeusovich_session.running = False
            if self.zeusovich_session._read_task:
                self.zeusovich_session._read_task.cancel()
                try:
                    await self.zeusovich_session._read_task
                except asyncio.CancelledError:
                    pass
            try:
                self.zeusovich_session.process.close()
            except Exception:
                pass
            self.zeusovich_session = None

    async def stop_zeusovich(self) -> bool:
        """Остановка Zeusovich"""
        async with self._lock:
            if self.zeusovich_session:
                await self._stop_zeusovich_session()
                return True
            return False

    def is_zeusovich_running(self) -> bool:
        """Проверка запущен ли Zeusovich"""
        return self.zeusovich_session is not None and self.zeusovich_session.running

    def get_zeusovich_history(self) -> str:
        """Получение истории Zeusovich"""
        if self.zeusovich_session:
            return self.zeusovich_session.output_history
        return ""

    def get_zeusovich_started_projects(self) -> set[str]:
        """Получение ID проектов, которые были при запуске Zeusovich"""
        if self.zeusovich_session:
            return self.zeusovich_session.started_project_ids
        return set()


# Глобальный экземпляр менеджера
process_manager = ProcessManager()
