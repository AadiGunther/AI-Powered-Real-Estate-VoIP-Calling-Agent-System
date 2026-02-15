from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect


active_notification_connections: Dict[int, Set[WebSocket]] = {}


async def register_connection(user_id: int, websocket: WebSocket) -> None:
    connections = active_notification_connections.get(user_id)
    if connections is None:
        connections = set()
        active_notification_connections[user_id] = connections
    connections.add(websocket)


async def unregister_connection(user_id: int, websocket: WebSocket) -> None:
    connections = active_notification_connections.get(user_id)
    if not connections:
        return
    if websocket in connections:
        connections.remove(websocket)
    if not connections:
        active_notification_connections.pop(user_id, None)


async def send_notification(user_id: int, payload: dict) -> None:
    connections = active_notification_connections.get(user_id)
    if not connections:
        return
    disconnected = []
    for ws in list(connections):
        try:
            await ws.send_json(payload)
        except WebSocketDisconnect:
            disconnected.append(ws)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connections.discard(ws)
    if not connections:
        active_notification_connections.pop(user_id, None)

