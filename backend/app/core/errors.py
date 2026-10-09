from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def install_error_handlers(app: FastAPI):
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": f"HTTP_{error.status_code}", "message": str(error.detail)}},
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return JSONResponse(status_code=422, content={
            "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed"}
        })
