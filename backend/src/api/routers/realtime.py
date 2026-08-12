"""WebSocket endpoints for real-time case and tenant updates.

Clients connect with a JWT in the `token` query parameter (WebSocket
upgrades in browsers don't support custom Authorization headers).
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from sqlalchemy import select

from src.auth.jwt import decode_token
from src.db import async_session_factory
from src.models import User
from src.realtime import get_hub

_log = logging.getLogger("watari.realtime.router")

router = APIRouter(tags=["realtime"])


async def _authenticate_ws(token: str) -> User | None:
    """Decode the token and load the user. Returns None on any failure."""
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.token_type != "access":
        return None
    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.id == payload.sub))
        ).scalar_one_or_none()
        if user is None or not user.is_active:
            return None
        return user


@router.websocket("/api/v1/realtime/cases/{case_id}")
async def case_stream(
    websocket: WebSocket,
    case_id: UUID,
    token: str = Query(...),
) -> None:
    user = await _authenticate_ws(token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    hub = get_hub()
    await hub.connect_case(websocket, str(case_id), str(user.id))
    try:
        while True:
            # Receive keepalive pings; refresh presence TTL on each ping
            message = await websocket.receive_text()
            if message == "ping":
                await hub._touch_presence(str(case_id), str(user.id))  # type: ignore[attr-defined]
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        _log.exception("case_stream error")
    finally:
        await hub.disconnect_case(websocket, str(case_id), str(user.id))


@router.websocket("/api/v1/realtime/tenants/{tenant_id}")
async def tenant_stream(
    websocket: WebSocket,
    tenant_id: UUID,
    token: str = Query(...),
) -> None:
    user = await _authenticate_ws(token)
    if user is None or user.tenant_id != tenant_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    hub = get_hub()
    await hub.connect_tenant(websocket, str(tenant_id))
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        _log.exception("tenant_stream error")
    finally:
        await hub.disconnect_tenant(websocket, str(tenant_id))


__all__ = ["router"]
