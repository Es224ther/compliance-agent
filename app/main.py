"""FastAPI application entry point for Compliance Agent."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware import add_api_middleware
from app.api.routes import router as api_router
from app.api.websocket import websocket_router
from app.rag.kb.vector_store import get_default_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.vector_store = get_default_store()
        app.state.kb_ready = True
    except Exception as exc:  # pragma: no cover
        app.state.vector_store = None
        app.state.kb_ready = False
        app.state.kb_error = str(exc)
    yield


app = FastAPI(title="Compliance Agent", version="0.4.0", lifespan=lifespan)
add_api_middleware(app)
app.include_router(api_router, prefix="/api/v1")
app.include_router(websocket_router)


@app.get("/health", tags=["system"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok", "version": "0.4.0"}


def main() -> None:
    """Local CLI entrypoint used by simple smoke runs."""

    print("Compliance Agent booting...")


if __name__ == "__main__":
    main()
