from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.event import router as event_router
from app.api.v1.health import router as health_router
from app.middleware import CSRFMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Team Battle CTF", version="1.0.0")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(event_router, prefix="/api/v1")
    app.add_middleware(CSRFMiddleware)
    return app


app = create_app()
