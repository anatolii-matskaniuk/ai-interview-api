import uuid
from fastapi import WebSocket
from typing import Dict


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[uuid.UUID, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: uuid.UUID):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: uuid.UUID):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_personal_message(self, message: dict, session_id: uuid.UUID):
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(message)


manager = ConnectionManager()
