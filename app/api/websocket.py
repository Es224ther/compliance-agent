"""WebSocket session manager and endpoint definitions."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from app.api.store import store
from app.orchestrator.pipeline import resume_pipeline

websocket_router = APIRouter()


class WebSocketSessionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[session_id].add(websocket)

    async def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.get(session_id, set()).discard(websocket)
            if not self._connections.get(session_id):
                self._connections.pop(session_id, None)

    async def broadcast(self, session_id: str, event: dict[str, Any]) -> None:
        encoded_event = jsonable_encoder(event)
        await store.append_event(session_id, encoded_event)
        async with self._lock:
            targets = list(self._connections.get(session_id, set()))
        stale: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(encoded_event)
            except RuntimeError:
                stale.append(websocket)
        for websocket in stale:
            await self.disconnect(session_id, websocket)

    async def replay(self, session_id: str, websocket: WebSocket) -> None:
        history = await store.get_event_history(session_id)
        for event in history:
            await websocket.send_json(event)


ws_manager = WebSocketSessionManager()


@websocket_router.websocket("/ws/{session_id}")
async def websocket_progress(websocket: WebSocket, session_id: str) -> None:
    await ws_manager.connect(session_id, websocket)
    await ws_manager.replay(session_id, websocket)

    try:
        while True:
            payload = await websocket.receive_json()
            if payload.get("type") not in {"followup_response", "followup_answers"}:
                continue

            state = await store.get_session_state(session_id)
            if state is None:
                await websocket.send_json(
                    {
                        "step": "followup",
                        "status": "error",
                        "message": "当前会话不存在或未进入追问状态",
                    }
                )
                continue

            user_followup = _normalize_followup_payload(payload)
            updated_state = await resume_pipeline(
                state,
                user_followup=user_followup,
                progress_callback=lambda event: ws_manager.broadcast(session_id, event),
            )
            await store.set_session_state(session_id, updated_state, updated_state.status.value.lower())
            if updated_state.report is not None:
                await store.complete_report(updated_state.report)
    except WebSocketDisconnect:
        await ws_manager.disconnect(session_id, websocket)


def _normalize_followup_payload(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("answer"), str):
        return payload["answer"]
    answers = payload.get("answers")
    if isinstance(answers, list):
        return "\n".join(str(item) for item in answers)
    if isinstance(answers, dict):
        return "\n".join(f"{key}: {value}" for key, value in answers.items())
    return ""
