from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request


def db(request: Request):
    return request.scope["env"].DB


async def rows(request: Request, statement: str, *values: Any):
    prepared = db(request).prepare(statement)
    if values:
        prepared = prepared.bind(*values)
    result = await prepared.all()
    return list(result.results)


async def first(request: Request, statement: str, *values: Any):
    prepared = db(request).prepare(statement)
    if values:
        prepared = prepared.bind(*values)
    return await prepared.first()


async def run(request: Request, statement: str, *values: Any):
    prepared = db(request).prepare(statement)
    if values:
        prepared = prepared.bind(*values)
    return await prepared.run()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_value(row: Any, field: str, default: Any = None) -> Any:
    value = getattr(row, field, default)
    return default if value is None and default is not None else value


def bool_value(row: Any, field: str) -> bool:
    return bool(row_value(row, field, 0))


def require_fields(payload: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        raise HTTPException(422, f"Missing fields: {', '.join(missing)}")


def encode_cursor(offset: int, fingerprint: str, secret: str) -> str:
    body = json.dumps(
        {"offset": offset, "query": fingerprint}, separators=(",", ":")
    ).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(body + signature).decode().rstrip("=")


def decode_cursor(cursor: str | None, fingerprint: str, secret: str) -> int:
    if cursor is None:
        return 0
    try:
        decoded = base64.b64decode(
            cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True
        )
        body, signature = decoded[:-32], decoded[-32:]
        expected = hmac.new(secret.encode(), body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(body)
        offset = payload["offset"]
        if payload["query"] != fingerprint or type(offset) is not int or not 0 <= offset <= 1_000_000:
            raise ValueError
        return offset
    except (ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        raise HTTPException(400, "Invalid cursor for this catalog query") from None


def env_value(request: Request, name: str, default: str | None = None) -> str:
    value = getattr(request.scope["env"], name, default)
    if value is None:
        raise HTTPException(503, f"Server configuration is missing: {name}")
    return str(value)

