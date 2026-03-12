"""FastAPI route definitions for the Compliance Agent API."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["system"])
async def healthcheck() -> dict[str, str]:
    """Basic liveness endpoint for local development."""

    return {"status": "ok"}
