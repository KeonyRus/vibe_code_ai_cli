"""
Zeusovich - CLI терминал с доступом ко всем проектам
Запускает LLM CLI в директории zeusovich-workspace (с junction ссылками)
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import load_all_projects
from ..process_manager import process_manager
from ..workspace import get_workspace_path

router = APIRouter()


class ZeusovichConnectionManager:
    """Менеджер WebSocket для Zeusovich терминала"""

    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

        async def send_output(data: str):
            await self.broadcast({
                "type": "output",
                "data": data
            })

        process_manager.add_zeusovich_callback(send_output)
        return send_output

    def disconnect(self, websocket: WebSocket, callback):
        if websocket in self.connections:
            self.connections.remove(websocket)
        process_manager.remove_zeusovich_callback(callback)

    async def broadcast(self, message: dict):
        disconnected = []
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.connections.remove(ws)


manager = ZeusovichConnectionManager()


@router.websocket("/terminal")
async def zeusovich_terminal(websocket: WebSocket):
    """WebSocket endpoint для Zeusovich CLI терминала"""
    callback = await manager.connect(websocket)

    # Отправляем статус
    is_running = process_manager.is_zeusovich_running()
    await websocket.send_json({
        "type": "status",
        "running": is_running
    })

    # Если уже запущен - отправляем историю
    if is_running:
        history = process_manager.get_zeusovich_history()
        if history:
            await websocket.send_json({
                "type": "history",
                "data": history
            })

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "input":
                await process_manager.write_to_zeusovich(data["data"])

            elif data["type"] == "resize":
                await process_manager.resize_zeusovich(
                    data["cols"],
                    data["rows"]
                )

            elif data["type"] == "start":
                if not process_manager.is_zeusovich_running():
                    # Используем workspace с junction ссылками
                    workspace_path = get_workspace_path()

                    # Запоминаем текущие проекты
                    projects = load_all_projects()
                    project_ids = {p.id for p in projects}

                    # Запускаем Claude CLI
                    await process_manager.start_zeusovich(workspace_path, project_ids)
                    await websocket.send_json({
                        "type": "status",
                        "running": True
                    })

            elif data["type"] == "stop":
                if process_manager.is_zeusovich_running():
                    await process_manager.stop_zeusovich()
                    await websocket.send_json({
                        "type": "status",
                        "running": False
                    })

    except WebSocketDisconnect:
        manager.disconnect(websocket, callback)
    except Exception as e:
        print(f"Zeusovich WebSocket error: {e}")
        manager.disconnect(websocket, callback)


@router.get("/status")
async def zeusovich_status():
    """
    Статус Zeusovich и информация о новых проектах.
    Возвращает running, и список проектов добавленных после запуска Zeusovich.
    """
    is_running = process_manager.is_zeusovich_running()

    result = {
        "running": is_running,
        "new_projects": [],
        "workspace_path": get_workspace_path()
    }

    if is_running:
        # Получаем проекты при запуске Zeusovich
        started_ids = process_manager.get_zeusovich_started_projects()

        # Получаем текущие проекты
        current_projects = load_all_projects()
        current_ids = {p.id for p in current_projects}

        # Находим новые проекты (есть сейчас, но не было при запуске)
        new_ids = current_ids - started_ids

        if new_ids:
            result["new_projects"] = [
                {"id": p.id, "name": p.name}
                for p in current_projects
                if p.id in new_ids
            ]

    return result
