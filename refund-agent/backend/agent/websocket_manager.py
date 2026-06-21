import time
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections = {}
        # Stores recent log entries in memory (for /admin/logs)
        self.all_logs = []

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def broadcast(self, tag: str, text: str, session_id: str):
        """Broadcast log entry to all connections in a session and append to history."""
        log_entry = {
            "timestamp": time.time(),
            "session_id": session_id,
            "tag": tag,  # 'TOOL', 'CHECK', 'DECISION', 'RESPONSE', 'ERROR'
            "text": text
        }
        self.all_logs.append(log_entry)
        
        # Keep only the last 100 logs in memory to save space
        if len(self.all_logs) > 100:
            self.all_logs.pop(0)

        if session_id in self.active_connections:
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_json(log_entry)
                except Exception:
                    # Ignore failures on closed sockets; disconnect will clean up
                    pass

manager = ConnectionManager()
