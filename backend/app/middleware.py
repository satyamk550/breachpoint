import secrets

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        unsafe = request.method in {"POST", "PUT", "PATCH", "DELETE"}
        if unsafe:
            cookie_token = request.cookies.get("csrf_token")
            header_token = request.headers.get("X-CSRF-Token")
            if (
                not cookie_token
                or not header_token
                or not secrets.compare_digest(cookie_token, header_token)
            ):
                return JSONResponse({"detail": "CSRF token missing or invalid"}, status_code=403)
        response = await call_next(request)
        if not request.cookies.get("csrf_token"):
            response.set_cookie(
                "csrf_token",
                secrets.token_urlsafe(32),
                httponly=False,
                samesite="lax",
                secure=not settings.debug,
            )
        return response
