from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from .database import get_db
from .security import get_current_user_ws
from . import models


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.user_rooms: Dict[int, Set[str]] = {}

    async def connect(self, websocket: WebSocket, user: models.User):
        await websocket.accept()
        if user.id not in self.active_connections:
            self.active_connections[user.id] = set()
        self.active_connections[user.id].add(websocket)
        self.user_rooms[user.id] = set()

    def disconnect(self, websocket: WebSocket, user: models.User):
        if user.id in self.active_connections:
            self.active_connections[user.id].discard(websocket)
            if not self.active_connections[user.id]:
                del self.active_connections[user.id]
                self.user_rooms.pop(user.id, None)

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            for ws in self.active_connections[user_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

    async def broadcast_to_room(self, message: dict, room: str, exclude_user: int = None):
        for user_id, rooms in self.user_rooms.items():
            if room in rooms and user_id != exclude_user:
                await self.send_personal_message(message, user_id)

    async def join_room(self, user_id: int, room: str):
        if user_id in self.user_rooms:
            self.user_rooms[user_id].add(room)

    async def leave_room(self, user_id: int, room: str):
        if user_id in self.user_rooms:
            self.user_rooms[user_id].discard(room)


manager = ConnectionManager()


async def websocket_endpoint(
    websocket: WebSocket,
    user: models.User = Depends(get_current_user_ws),
    db: Session = Depends(get_db),
):
    await manager.connect(websocket, user)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if action == "join":
                room = data.get("room")
                if room:
                    await manager.join_room(user.id, room)
                    await websocket.send_json({"type": "joined", "room": room})
            elif action == "leave":
                room = data.get("room")
                if room:
                    await manager.leave_room(user.id, room)
                    await websocket.send_json({"type": "left", "room": room})
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, user)
    except Exception:
        manager.disconnect(websocket, user)


async def notify_inventory_update(
    campaign_id: int,
    article_id: int,
    action: str,
    user_id: int,
    data: dict = None,
):
    message = {
        "type": "inventory_update",
        "campaign_id": campaign_id,
        "article_id": article_id,
        "action": action,
        "user_id": user_id,
        "data": data or {},
    }
    await manager.broadcast_to_room(message, f"inventory:{campaign_id}", exclude_user=user_id)


async def notify_notification(user_id: int, notification: dict):
    message = {"type": "notification", "data": notification}
    await manager.send_personal_message(message, user_id)


async def notify_issue_update(issue_id: int, action: str, user_id: int, data: dict = None):
    message = {
        "type": "issue_update",
        "issue_id": issue_id,
        "action": action,
        "user_id": user_id,
        "data": data or {},
    }
    await manager.broadcast_to_room(message, "issues", exclude_user=user_id)