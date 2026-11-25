from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.auth import router as auth_router
from app.api.v1.challenges import router as challenges_router
from app.api.v1.event import router as event_router
from app.api.v1.health import router as health_router
from app.api.v1.teams import router as teams_router
from app.api.v1.phase4b import router as phase4b_router
from app.middleware import CSRFMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Team Battle CTF", version="1.0.0")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(event_router, prefix="/api/v1")
    app.include_router(teams_router, prefix="/api/v1")
    app.include_router(challenges_router, prefix="/api/v1")
    app.include_router(phase4b_router, prefix="/api/v1")
    app.add_middleware(CSRFMiddleware)

    @app.exception_handler(RequestValidationError)
    async def sanitize_flag_validation_errors(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        if "/flags" in request.url.path:
            errors = [
                {key: value for key, value in error.items() if key != "input"} for error in errors
            ]
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})

    return app


app = create_app()
# ruff: noqa: I001
