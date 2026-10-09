import logging

from starlette.datastructures import MutableHeaders
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class ApiCORSMiddleware(CORSMiddleware):
    def preflight_response(self, request_headers):
        response = super().preflight_response(request_headers)
        if response.status_code == 400:
            headers = {key: value for key, value in response.headers.items()
                       if key not in {"content-type", "content-length"}}
            return JSONResponse({"error": {"code": "HTTP_400", "message": "CORS request denied"}},
                                status_code=400, headers=headers)
        return response


class SafeErrorsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def track(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, track)
        except Exception as error:
            # Exception messages/tracebacks may contain SQL parameters or credentials.
            logger.error("Unhandled request error: %s", type(error).__name__)
            if started:
                raise
            await JSONResponse(
                {"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred"}},
                status_code=500,
            )(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app, production=False):
        self.app = app
        self.production = production

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def secured(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                if scope["path"].startswith("/api/"):
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; frame-ancestors 'none'"
                    )
                if message["status"] >= 400:
                    headers["Cache-Control"] = "no-store"
                if self.production and scope["scheme"] == "https":
                    headers["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        await self.app(scope, receive, secured)


def install_http_middleware(app, settings):
    # add_middleware prepends: security headers -> CORS -> safe errors -> routes.
    app.add_middleware(SafeErrorsMiddleware)
    app.add_middleware(ApiCORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type"], allow_credentials=False)
    app.add_middleware(SecurityHeadersMiddleware, production=settings.app_env == "production")
