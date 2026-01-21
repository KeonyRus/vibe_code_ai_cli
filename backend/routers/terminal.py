"""
WebSocket роутер для терминала
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional

from ..process_manager import process_manager
from ..config import load_project

router = APIRouter()


class ConnectionManager:
    """Менеджер WebSocket соединений"""

    def __init__(self):
        # project_id -> list of websockets
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        """Подключение нового клиента"""
        await websocket.accept()

        if project_id not in self.connections:
            self.connections[project_id] = []
        self.connections[project_id].append(websocket)

        # Регистрируем callback для получения вывода
        async def send_output(data: str):
            await self.broadcast(project_id, {
                "type": "output",
                "data": data
            })

        # Регистрируем callback для статуса (typing/idle)
        async def send_status(status: str):
            await self.broadcast(project_id, {
                "type": "llm_status",
                "status": status  # "typing" или "idle"
            })

        process_manager.add_output_callback(project_id, send_output)
        process_manager.add_status_callback(project_id, send_status)

        return (send_output, send_status)

    def disconnect(self, websocket: WebSocket, project_id: str, callbacks):
        """Отключение клиента"""
        if project_id in self.connections:
            if websocket in self.connections[project_id]:
                self.connections[project_id].remove(websocket)
            if not self.connections[project_id]:
                del self.connections[project_id]

        output_cb, status_cb = callbacks
        process_manager.remove_output_callback(project_id, output_cb)
        process_manager.remove_status_callback(project_id, status_cb)

    async def broadcast(self, project_id: str, message: dict):
        """Отправка сообщения всем клиентам проекта"""
        if project_id in self.connections:
            disconnected = []
            for ws in self.connections[project_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(ws)

            # Удаляем отключенные соединения
            for ws in disconnected:
                self.connections[project_id].remove(ws)


manager = ConnectionManager()


@router.websocket("/{project_id}")
async def terminal_websocket(websocket: WebSocket, project_id: str):
    """WebSocket endpoint для терминала проекта"""
    project = load_project(project_id)
    if not project:
        await websocket.close(code=4004, reason="Project not found")
        return

    callbacks = await manager.connect(websocket, project_id)

    # Отправляем начальный статус
    is_running = process_manager.is_running(project_id)
    await websocket.send_json({
        "type": "status",
        "running": is_running,
        "project": project.model_dump()
    })

    # Если процесс запущен - отправляем историю
    if is_running:
        history = process_manager.get_output_history(project_id)
        if history:
            await websocket.send_json({
                "type": "history",
                "data": history
            })

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "input":
                # Ввод пользователя
                await process_manager.write_to_process(
                    project_id,
                    data["data"]
                )

            elif data["type"] == "resize":
                # Изменение размера терминала
                await process_manager.resize_terminal(
                    project_id,
                    data["cols"],
                    data["rows"]
                )

            elif data["type"] == "start":
                # Запуск процесса
                print(f"[DEBUG] Start requested for {project_id}")
                if not process_manager.is_running(project_id):
                    print(f"[DEBUG] Starting process...")
                    await process_manager.start_process(project)
                    print(f"[DEBUG] Process started!")
                    await websocket.send_json({
                        "type": "status",
                        "running": True
                    })

            elif data["type"] == "stop":
                # Остановка процесса
                if process_manager.is_running(project_id):
                    await process_manager.stop_process(project_id)
                    await websocket.send_json({
                        "type": "status",
                        "running": False
                    })

    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id, callbacks)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, project_id, callbacks)


# ==================== CONSOLE WEBSOCKET ====================

class ConsoleConnectionManager:
    """Менеджер WebSocket для консолей"""

    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()

        if project_id not in self.connections:
            self.connections[project_id] = []
        self.connections[project_id].append(websocket)

        async def send_output(data: str):
            await self.broadcast(project_id, {
                "type": "output",
                "data": data
            })

        process_manager.add_console_callback(project_id, send_output)
        return send_output

    def disconnect(self, websocket: WebSocket, project_id: str, callback):
        if project_id in self.connections:
            if websocket in self.connections[project_id]:
                self.connections[project_id].remove(websocket)
            if not self.connections[project_id]:
                del self.connections[project_id]
        process_manager.remove_console_callback(project_id, callback)

    async def broadcast(self, project_id: str, message: dict):
        if project_id in self.connections:
            disconnected = []
            for ws in self.connections[project_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                self.connections[project_id].remove(ws)


console_manager = ConsoleConnectionManager()


@router.websocket("/console/{project_id}")
async def console_websocket(websocket: WebSocket, project_id: str):
    """WebSocket endpoint для консоли проекта"""
    project = load_project(project_id)
    if not project:
        await websocket.close(code=4004, reason="Project not found")
        return

    callback = await console_manager.connect(websocket, project_id)

    # Отправляем статус
    is_running = process_manager.is_console_running(project_id)
    await websocket.send_json({
        "type": "status",
        "running": is_running
    })

    # Если консоль уже запущена - отправляем историю
    if is_running:
        history = process_manager.get_console_history(project_id)
        if history:
            await websocket.send_json({
                "type": "history",
                "data": history
            })

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "input":
                await process_manager.write_to_console(project_id, data["data"])

            elif data["type"] == "resize":
                await process_manager.resize_console(
                    project_id,
                    data["cols"],
                    data["rows"]
                )

            elif data["type"] == "start":
                if not process_manager.is_console_running(project_id):
                    await process_manager.start_console(project_id, project.path)
                    await websocket.send_json({
                        "type": "status",
                        "running": True
                    })

            elif data["type"] == "stop":
                if process_manager.is_console_running(project_id):
                    await process_manager.stop_console(project_id)
                    await websocket.send_json({
                        "type": "status",
                        "running": False
                    })

    except WebSocketDisconnect:
        console_manager.disconnect(websocket, project_id, callback)
    except Exception as e:
        print(f"Console WebSocket error: {e}")
        console_manager.disconnect(websocket, project_id, callback)
