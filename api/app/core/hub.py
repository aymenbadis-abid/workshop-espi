from fastapi import WebSocket


class Hub:
    """Fan-out of live events to dashboard WebSocket clients."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    def add(self, websocket: WebSocket) -> None:
        self._clients.add(websocket)

    def discard(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self._clients):
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self._clients.discard(websocket)


hub = Hub()
