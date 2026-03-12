"""FastAPI application entry point for Compliance Agent."""

from fastapi import FastAPI

from app.api.routes import router as api_router

app = FastAPI(title="Compliance Agent", version="0.1.0")
app.include_router(api_router)


def main() -> None:
    """Local CLI entrypoint used by simple smoke runs."""

    print("Compliance Agent booting...")


if __name__ == "__main__":
    main()
