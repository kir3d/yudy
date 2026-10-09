from __future__ import annotations

import hashlib
import json
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import urlencode

import asgi
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from workers import fetch

from auth import authenticate, current_user, delete_auth_user, refresh_session, require_consent
from ai_privacy import AI_EXCLUDED_FIELDS, AI_PROFILE_FIELDS
from core import (
    bool_value,
    decode_cursor,
    encode_cursor,
    env_value,
    first,
    now,
    require_fields,
    row_value,
    rows,
    run,
)
from xstocks import ai_selection, coingecko_markets, market_fields, official_catalog, quote, source_timestamp


app = FastAPI(title="YUDY API", version="0.2.0-cloudflare", debug=False)


@app.middleware("http")
async def response_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        response = await call_next(request)
    origins = {
        origin.strip()
        for origin in env_value(request, "CORS_ORIGINS", "").split(",")
        if origin.strip()
    }
    origin = request.headers.get("origin")
    if origin and origin in origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization,Content-Type"
        response.headers["Vary"] = "Origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/v1/auth") or request.url.path in {
        "/api/v1/users/me",
        "/api/v1/profile",
    }:
        response.headers["Cache-Control"] = "no-store"
    return response


async def auth_rate_limit(request: Request) -> None:
    limiter = getattr(request.scope["env"], "AUTH_RATE_LIMITER", None)
    if limiter is None:
        return
    key = request.headers.get("cf-connecting-ip") or "local"
    try:
        from js import Object
        from pyodide.ffi import to_js

        options = to_js({"key": key}, dict_converter=Object.fromEntries)
        outcome = await limiter.limit(options)
        if not bool(outcome.success):
            raise HTTPException(429, "Too many authentication attempts")
    except HTTPException:
        raise
    except Exception:
        if env_value(request, "APP_ENV", "development") == "production":
            raise HTTPException(503, "Authentication rate limiter is unavailable") from None


@app.get("/health")
async def health(request: Request):
    result = await first(request, "SELECT 1 AS ready")
    return {"data": {"status": "ok", "database": bool(result and result.ready)}, "meta": {}}


@app.post("/api/v1/auth/register", status_code=201)
async def register(request: Request, payload: dict[str, Any]):
    await auth_rate_limit(request)
    data = await authenticate(request, payload, "/auth/v1/signup")
    await record_event(request, "registration_completed", data["user"]["id"])
    return {"data": data, "meta": {}}


@app.post("/api/v1/auth/login")
async def login(request: Request, payload: dict[str, Any]):
    await auth_rate_limit(request)
    data = await authenticate(request, payload, "/auth/v1/token?grant_type=password")
    return {"data": data, "meta": {}}


@app.post("/api/v1/auth/refresh")
async def refresh(request: Request, payload: dict[str, Any]):
    await auth_rate_limit(request)
    token = str(payload.get("refresh_token", ""))
    return {"data": await refresh_session(request, token), "meta": {}}


@app.post("/api/v1/auth/logout", status_code=204)
async def logout(request: Request, payload: dict[str, Any]):
    token = str(payload.get("refresh_token", ""))
    if token:
        from auth import _supabase

        refreshed = await _supabase(
            request,
            "/auth/v1/token?grant_type=refresh_token",
            payload={"refresh_token": token},
        )
        if refreshed.status == 200:
            session = await refreshed.json()
            access_token = session.get("access_token")
            if access_token:
                await _supabase(request, "/auth/v1/logout", bearer=str(access_token))
    return Response(status_code=204)


@app.get("/api/v1/users/me")
async def me(request: Request, user: dict[str, str] = Depends(current_user)):
    record = await first(
        request,
        "SELECT agreements_accepted_at FROM users WHERE id = ?",
        user["id"],
    )
    return {
        "data": {
            **user,
            "agreements_accepted_at": row_value(record, "agreements_accepted_at"),
        },
        "meta": {},
    }


@app.delete("/api/v1/users/me", status_code=204)
async def delete_me(
    request: Request,
    user: dict[str, str] = Depends(current_user),
):
    await run(
        request,
        "UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?",
        now(),
        user["id"],
    )
    try:
        await delete_auth_user(request, user["id"])
    except Exception:
        await run(
            request,
            "UPDATE users SET is_active = 1, updated_at = ? WHERE id = ?",
            now(),
            user["id"],
        )
        raise
    database = request.scope["env"].DB
    statements = [
        database.prepare(f"DELETE FROM {table} WHERE user_id = ?").bind(user["id"])
        for table in (
            "user_consents",
            "user_goals",
            "user_interests",
            "user_excluded_interests",
            "user_regions",
            "user_profiles",
            "risk_profiles",
            "asset_interaction_states",
            "asset_interactions",
            "xstock_interaction_states",
            "xstock_interactions",
            "analytics_events",
        )
    ]
    anonymous_email = f"deleted+{hashlib.sha256(user['id'].encode()).hexdigest()[:24]}@yudyai.invalid"
    statements.append(
        database.prepare(
            "UPDATE users SET email = ?, is_active = 0, agreements_accepted_at = NULL, updated_at = ? WHERE id = ?"
        ).bind(anonymous_email, now(), user["id"])
    )
    await database.batch(statements)
    return Response(status_code=204)


async def record_event(
    request: Request,
    event_name: str,
    user_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> None:
    await run(
        request,
        "INSERT INTO analytics_events (id, user_id, event_name, properties, created_at) VALUES (?, ?, ?, ?, ?)",
        str(uuid.uuid4()),
        user_id,
        event_name,
        json.dumps(properties or {}, separators=(",", ":")),
        now(),
    )


def legal_document(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "type": row.type,
        "version": row.version,
        "title": row.title,
        "content": row.content,
        "is_mandatory": bool(row.is_mandatory),
    }


@app.get("/api/v1/legal/documents")
async def legal_documents(request: Request):
    data = await rows(
        request,
        "SELECT * FROM legal_documents WHERE active = 1 ORDER BY type, version",
    )
    return {"data": [legal_document(row) for row in data], "meta": {}}


async def consent_state(request: Request, user_id: str) -> dict[str, Any]:
    data = await rows(
        request,
        """
        SELECT d.*, c.accepted_at
        FROM legal_documents d
        LEFT JOIN user_consents c
          ON c.legal_document_id = d.id AND c.user_id = ?
        WHERE d.active = 1
        ORDER BY d.type, d.version
        """,
        user_id,
    )
    documents = [
        {
            **legal_document(row),
            "accepted": row_value(row, "accepted_at") is not None,
            "accepted_at": row_value(row, "accepted_at"),
        }
        for row in data
    ]
    required_types = {"TERMS_OF_USE", "PRIVACY_POLICY", "PERSONAL_DATA_CONSENT"}
    accepted_types = {
        row.type
        for row in data
        if bool(row.is_mandatory) and row_value(row, "accepted_at") is not None
    }
    mandatory_complete = all(
        row_value(row, "accepted_at") is not None for row in data if bool(row.is_mandatory)
    )
    user = await first(
        request,
        "SELECT agreements_accepted_at FROM users WHERE id = ?",
        user_id,
    )
    return {
        "documents": documents,
        "all_required_accepted": mandatory_complete and accepted_types == required_types,
        "agreements_accepted_at": row_value(user, "agreements_accepted_at"),
    }


@app.get("/api/v1/legal/consents/me")
async def my_consents(
    request: Request, user: dict[str, str] = Depends(current_user)
):
    return {"data": await consent_state(request, user["id"]), "meta": {}}


@app.post("/api/v1/legal/consents")
async def accept_consents(
    request: Request,
    payload: dict[str, Any],
    user: dict[str, str] = Depends(current_user),
):
    supplied = payload.get("consents")
    if not isinstance(supplied, list) or not 1 <= len(supplied) <= 20:
        raise HTTPException(422, "Provide one or more legal consents")
    ids = [str(item.get("document_id", "")) for item in supplied if isinstance(item, dict)]
    if len(ids) != len(supplied) or len(set(ids)) != len(ids):
        raise HTTPException(422, "Document ids must be present and unique")
    placeholders = ",".join("?" for _ in ids)
    current = await rows(
        request,
        f"SELECT id, version FROM legal_documents WHERE active = 1 AND id IN ({placeholders})",
        *ids,
    )
    versions = {row.id: row.version for row in current}
    for item in supplied:
        document_id = str(item["document_id"])
        if item.get("accepted") is not True or versions.get(document_id) != item.get("version"):
            raise HTTPException(409, "Documents changed. Review the current versions.")
    stamp = now()
    for document_id in ids:
        await run(
            request,
            "INSERT OR IGNORE INTO user_consents (id, user_id, legal_document_id, accepted_at) VALUES (?, ?, ?, ?)",
            str(uuid.uuid4()),
            user["id"],
            document_id,
            stamp,
        )
    state = await consent_state(request, user["id"])
    if state["all_required_accepted"]:
        latest = await first(
            request,
            """
            SELECT MAX(c.accepted_at) AS accepted_at
            FROM user_consents c
            JOIN legal_documents d ON d.id = c.legal_document_id
            WHERE c.user_id = ? AND d.active = 1 AND d.is_mandatory = 1
            """,
            user["id"],
        )
        accepted_at = row_value(latest, "accepted_at")
        await run(
            request,
            "UPDATE users SET agreements_accepted_at = ?, updated_at = ? WHERE id = ?",
            accepted_at,
            stamp,
            user["id"],
        )
        state["agreements_accepted_at"] = accepted_at
    await record_event(
        request,
        "legal_accepted",
        user["id"],
        {"documents": supplied},
    )
    return {"data": state, "meta": {}}


def taxonomy_item(row: Any) -> dict[str, str]:
    return {"id": row.id, "code": row.code, "title": row.title}


@app.get("/api/v1/goals")
async def goals(request: Request):
    data = await rows(request, "SELECT id, code, title FROM goals WHERE active = 1 ORDER BY title")
    return {"data": [taxonomy_item(row) for row in data], "meta": {}}


@app.get("/api/v1/interests")
async def interests(request: Request):
    data = await rows(request, "SELECT id, code, title FROM interests WHERE active = 1 ORDER BY title")
    return {"data": [taxonomy_item(row) for row in data], "meta": {}}


@app.get("/api/v1/regions")
async def regions(request: Request):
    data = await rows(request, "SELECT id, code, title FROM regions WHERE active = 1 ORDER BY title")
    return {"data": [taxonomy_item(row) for row in data], "meta": {}}


PROFILE_SELECTIONS = {
    "goal_ids": ("goals", "user_goals", "goal_id"),
    "interest_ids": ("interests", "user_interests", "interest_id"),
    "excluded_interest_ids": ("interests", "user_excluded_interests", "interest_id"),
    "region_ids": ("regions", "user_regions", "region_id"),
}


async def profile_data(request: Request, user_id: str) -> dict[str, Any]:
    profile = await first(request, "SELECT * FROM user_profiles WHERE user_id = ?", user_id)
    if profile is None:
        raise HTTPException(404, "Complete onboarding to create your profile")
    result: dict[str, Any] = {
        "experience": profile.experience,
        "investment_horizon": profile.investment_horizon,
        "onboarding_completed": bool(profile.onboarding_completed),
    }
    for name, (_, table, column) in PROFILE_SELECTIONS.items():
        selected = await rows(
            request,
            f"SELECT {column} AS id FROM {table} WHERE user_id = ? ORDER BY {column}",
            user_id,
        )
        result[name] = [row.id for row in selected]
    return result


def validate_profile(payload: dict[str, Any]) -> None:
    require_fields(payload, "experience", "investment_horizon", "goal_ids")
    if payload["experience"] not in {"NEW", "SOME", "REGULAR", "EXPERIENCED"}:
        raise HTTPException(422, "Invalid experience")
    if payload["investment_horizon"] not in {"UNDER_ONE", "ONE_THREE", "THREE_FIVE", "FIVE_PLUS"}:
        raise HTTPException(422, "Invalid investment horizon")
    for name in PROFILE_SELECTIONS:
        value = payload.get(name, [])
        if not isinstance(value, list) or len(value) > 50 or len(set(value)) != len(value):
            raise HTTPException(422, f"Invalid selections in {name}")
    if not payload["goal_ids"]:
        raise HTTPException(422, "Select at least one goal")
    if set(payload.get("interest_ids", [])) & set(payload.get("excluded_interest_ids", [])):
        raise HTTPException(422, "Interests and exclusions must not overlap")


async def save_profile(
    request: Request, payload: dict[str, Any], user_id: str, create: bool
) -> dict[str, Any]:
    validate_profile(payload)
    existing = await first(request, "SELECT user_id FROM user_profiles WHERE user_id = ?", user_id)
    if existing is None and not create:
        raise HTTPException(404, "Profile does not exist")
    for name, (taxonomy, _, _) in PROFILE_SELECTIONS.items():
        selected = [str(value) for value in payload.get(name, [])]
        if selected:
            placeholders = ",".join("?" for _ in selected)
            valid = await rows(
                request,
                f"SELECT id FROM {taxonomy} WHERE active = 1 AND id IN ({placeholders})",
                *selected,
            )
            if {row.id for row in valid} != set(selected):
                raise HTTPException(422, f"Unknown or inactive selection in {name}")
    stamp = now()
    await run(
        request,
        """
        INSERT INTO user_profiles
          (user_id, experience, investment_horizon, onboarding_completed, created_at, updated_at)
        VALUES (?, ?, ?, 1, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
          experience = excluded.experience,
          investment_horizon = excluded.investment_horizon,
          onboarding_completed = 1,
          updated_at = excluded.updated_at
        """,
        user_id,
        payload["experience"],
        payload["investment_horizon"],
        stamp,
        stamp,
    )
    for name, (_, table, column) in PROFILE_SELECTIONS.items():
        await run(request, f"DELETE FROM {table} WHERE user_id = ?", user_id)
        for selected_id in payload.get(name, []):
            await run(
                request,
                f"INSERT INTO {table} (user_id, {column}) VALUES (?, ?)",
                user_id,
                str(selected_id),
            )
    if existing is None:
        await record_event(request, "onboarding_completed", user_id)
    return await profile_data(request, user_id)


@app.get("/api/v1/profile")
async def get_profile(
    request: Request, user: dict[str, str] = Depends(require_consent)
):
    return {"data": await profile_data(request, user["id"]), "meta": {}}


@app.post("/api/v1/profile/onboarding")
async def onboarding(
    request: Request,
    payload: dict[str, Any],
    user: dict[str, str] = Depends(require_consent),
):
    return {"data": await save_profile(request, payload, user["id"], True), "meta": {}}


@app.put("/api/v1/profile")
async def update_profile(
    request: Request,
    payload: dict[str, Any],
    user: dict[str, str] = Depends(require_consent),
):
    return {"data": await save_profile(request, payload, user["id"], False), "meta": {}}


async def require_onboarding(request: Request, user_id: str) -> None:
    row = await first(
        request,
        "SELECT onboarding_completed FROM user_profiles WHERE user_id = ?",
        user_id,
    )
    if row is None or not bool(row.onboarding_completed):
        raise HTTPException(403, "Complete onboarding before risk assessment")


async def current_questionnaire(request: Request):
    questionnaire = await first(
        request,
        "SELECT * FROM risk_questionnaires WHERE active = 1 LIMIT 1",
    )
    if questionnaire is None:
        raise HTTPException(503, "Risk questionnaire is unavailable")
    return questionnaire


@app.get("/api/v1/risk/questions")
async def risk_questions(
    request: Request, user: dict[str, str] = Depends(require_consent)
):
    await require_onboarding(request, user["id"])
    questionnaire = await current_questionnaire(request)
    questions = await rows(
        request,
        "SELECT * FROM risk_questions WHERE questionnaire_id = ? AND active = 1 ORDER BY sort_order, id",
        questionnaire.id,
    )
    options = await rows(
        request,
        """
        SELECT o.* FROM risk_answer_options o
        JOIN risk_questions q ON q.id = o.question_id
        WHERE q.questionnaire_id = ? AND q.active = 1
        ORDER BY q.sort_order, o.sort_order, o.id
        """,
        questionnaire.id,
    )
    if not questions or any(not any(o.question_id == q.id for o in options) for q in questions):
        raise HTTPException(503, "Risk questionnaire is incomplete")
    return {
        "data": {
            "questionnaire_version": questionnaire.version,
            "questions": [
                {
                    "id": question.id,
                    "code": question.code,
                    "text": question.text,
                    "sort_order": question.sort_order,
                    "options": [
                        {"id": option.id, "text": option.text, "sort_order": option.sort_order}
                        for option in options
                        if option.question_id == question.id
                    ],
                }
                for question in questions
            ],
        },
        "meta": {},
    }


def normalized_risk_score(total: int, maximum: int) -> int:
    if maximum <= 0 or not 0 <= total <= maximum:
        raise HTTPException(503, "Risk questionnaire scoring is invalid")
    return (total * 200 + maximum) // (maximum * 2)


def risk_category(score: int, conservative_max: int, balanced_max: int) -> str:
    if score <= conservative_max:
        return "Conservative"
    if score <= balanced_max:
        return "Balanced"
    return "Growth"


@app.post("/api/v1/risk/assessment")
async def assess_risk(
    request: Request,
    payload: dict[str, Any],
    user: dict[str, str] = Depends(require_consent),
):
    await require_onboarding(request, user["id"])
    questionnaire = await current_questionnaire(request)
    if payload.get("questionnaire_version") != questionnaire.version:
        raise HTTPException(409, "Questionnaire was updated. Reload and answer the current version")
    answers = payload.get("answers")
    if not isinstance(answers, list) or not answers:
        raise HTTPException(422, "Answer every current question exactly once")
    questions = await rows(
        request,
        "SELECT id FROM risk_questions WHERE questionnaire_id = ? AND active = 1",
        questionnaire.id,
    )
    question_ids = {question.id for question in questions}
    supplied_ids = {str(answer.get("question_id", "")) for answer in answers if isinstance(answer, dict)}
    if supplied_ids != question_ids or len(supplied_ids) != len(answers):
        raise HTTPException(422, "Answer every current question exactly once")
    options = await rows(
        request,
        """
        SELECT o.id, o.question_id, o.score
        FROM risk_answer_options o
        JOIN risk_questions q ON q.id = o.question_id
        WHERE q.questionnaire_id = ? AND q.active = 1
        """,
        questionnaire.id,
    )
    by_id = {option.id: option for option in options}
    total = 0
    for answer in answers:
        option = by_id.get(str(answer.get("option_id", "")))
        if option is None or option.question_id != str(answer.get("question_id", "")):
            raise HTTPException(422, "Answer option does not belong to its question")
        total += int(option.score)
    maximum = sum(
        max(int(option.score) for option in options if option.question_id == question_id)
        for question_id in question_ids
    )
    score = normalized_risk_score(total, maximum)
    category = risk_category(score, int(questionnaire.conservative_max), int(questionnaire.balanced_max))
    stamp = now()
    await run(
        request,
        """
        INSERT INTO risk_profiles
          (user_id, risk_score, risk_category, questionnaire_version, answers, calculated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
          risk_score = excluded.risk_score,
          risk_category = excluded.risk_category,
          questionnaire_version = excluded.questionnaire_version,
          answers = excluded.answers,
          calculated_at = excluded.calculated_at
        """,
        user["id"],
        score,
        category,
        questionnaire.version,
        json.dumps(answers, separators=(",", ":")),
        stamp,
    )
    await record_event(
        request,
        "risk_profile_completed",
        user["id"],
        {"questionnaire_version": questionnaire.version},
    )
    return {
        "data": {
            "risk_score": score,
            "risk_category": category,
            "questionnaire_version": questionnaire.version,
            "calculated_at": stamp,
            "is_current": True,
        },
        "meta": {},
    }


@app.get("/api/v1/risk/profile")
async def get_risk_profile(
    request: Request, user: dict[str, str] = Depends(require_consent)
):
    await require_onboarding(request, user["id"])
    profile = await first(request, "SELECT * FROM risk_profiles WHERE user_id = ?", user["id"])
    if profile is None:
        raise HTTPException(404, "Complete the risk questionnaire to create a risk profile")
    questionnaire = await current_questionnaire(request)
    return {
        "data": {
            "risk_score": profile.risk_score,
            "risk_category": profile.risk_category,
            "questionnaire_version": profile.questionnaire_version,
            "calculated_at": profile.calculated_at,
            "is_current": profile.questionnaire_version == questionnaire.version,
        },
        "meta": {},
    }


ASSET_SUMMARY_SQL = """
SELECT
  a.*,
  (SELECT p.close FROM asset_prices p WHERE p.asset_id = a.id ORDER BY p.timestamp DESC LIMIT 1) AS price,
  (SELECT p.timestamp FROM asset_prices p WHERE p.asset_id = a.id ORDER BY p.timestamp DESC LIMIT 1) AS as_of,
  (SELECT p.close FROM asset_prices p WHERE p.asset_id = a.id ORDER BY p.timestamp DESC LIMIT 1) AS latest_close,
  (SELECT p.close FROM asset_prices p WHERE p.asset_id = a.id
     AND julianday(p.timestamp) >= julianday((SELECT MAX(p2.timestamp) FROM asset_prices p2 WHERE p2.asset_id = a.id)) - 365
     ORDER BY p.timestamp ASC LIMIT 1) AS year_start_close,
  EXISTS(SELECT 1 FROM tokenized_assets t WHERE t.asset_id = a.id AND t.active = 1) AS has_tokenized_representation,
  EXISTS(SELECT 1 FROM asset_fundamentals f WHERE f.asset_id = a.id AND f.dividend > 0) AS has_dividend
FROM assets a
"""


def performance(first_close: Any, latest_close: Any) -> float | None:
    if first_close is None or latest_close is None or float(first_close) == 0:
        return None
    return round((float(latest_close) / float(first_close) - 1) * 100, 2)


def asset_summary(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "name": row.name,
        "asset_type": row.asset_type,
        "sector": row_value(row, "sector"),
        "industry": row_value(row, "industry"),
        "region": row_value(row, "region"),
        "market": row_value(row, "market"),
        "currency": row.currency,
        "price": row_value(row, "price"),
        "as_of": row_value(row, "as_of"),
        "performance_1y": performance(
            row_value(row, "year_start_close"), row_value(row, "latest_close")
        ),
        "has_tokenized_representation": bool(row.has_tokenized_representation),
    }


def history_cutoff(period: str, latest: str | None) -> str | None:
    if latest is None or period == "ALL":
        return None
    days = {"1D": 1, "1M": 30, "1Y": 365, "3Y": 1095}.get(period)
    if days is None:
        raise HTTPException(422, "Invalid history period")
    parsed = datetime.fromisoformat(latest.replace("Z", "+00:00"))
    return (parsed - timedelta(days=days)).isoformat()


async def asset_history(request: Request, asset_id: str, period: str) -> dict[str, Any]:
    latest = await first(
        request,
        "SELECT timestamp FROM asset_prices WHERE asset_id = ? ORDER BY timestamp DESC LIMIT 1",
        asset_id,
    )
    cutoff = history_cutoff(period, latest.timestamp if latest else None)
    if cutoff is None:
        data = await rows(
            request,
            "SELECT timestamp, close FROM asset_prices WHERE asset_id = ? ORDER BY timestamp",
            asset_id,
        )
    else:
        data = await rows(
            request,
            "SELECT timestamp, close FROM asset_prices WHERE asset_id = ? AND timestamp >= ? ORDER BY timestamp",
            asset_id,
            cutoff,
        )
    return {
        "period": period,
        "points": [{"timestamp": point.timestamp, "close": point.close} for point in data],
        "performance_percent": performance(data[0].close, data[-1].close) if len(data) >= 2 else None,
    }


async def require_asset(request: Request, asset_id: str):
    asset = await first(request, f"{ASSET_SUMMARY_SQL} WHERE a.id = ? AND a.active = 1", asset_id)
    if asset is None:
        raise HTTPException(404, "Asset is unavailable")
    return asset


@app.get("/api/v1/assets/filters")
async def asset_filters(request: Request):
    async def options(column: str):
        data = await rows(
            request,
            f"SELECT DISTINCT {column} AS value FROM assets WHERE active = 1 AND {column} IS NOT NULL ORDER BY {column}",
        )
        return [
            {"code": str(row.value), "title": str(row.value).replace("_", " ").title()}
            for row in data
        ]

    regions_data = await rows(
        request,
        """
        SELECT DISTINCT a.region AS code, COALESCE(r.title, a.region) AS title
        FROM assets a LEFT JOIN regions r ON r.code = a.region
        WHERE a.active = 1 AND a.region IS NOT NULL ORDER BY title
        """,
    )
    themes_data = await rows(
        request,
        """
        SELECT DISTINCT i.code, i.title FROM interests i
        JOIN asset_themes at ON at.interest_id = i.id
        JOIN assets a ON a.id = at.asset_id
        WHERE i.active = 1 AND i.kind = 'THEME' AND a.active = 1 ORDER BY i.title
        """,
    )
    return {
        "data": {
            "regions": [{"code": row.code, "title": row.title} for row in regions_data],
            "markets": await options("market"),
            "sectors": await options("sector"),
            "industries": await options("industry"),
            "themes": [{"code": row.code, "title": row.title} for row in themes_data],
            "asset_types": await options("asset_type"),
        },
        "meta": {"data_mode": "demo"},
    }


@app.get("/api/v1/assets")
async def asset_catalog(
    request: Request,
    search: str | None = Query(default=None, max_length=100),
    region: str | None = Query(default=None, max_length=128),
    market: str | None = Query(default=None, max_length=128),
    sector: str | None = Query(default=None, max_length=128),
    industry: str | None = Query(default=None, max_length=128),
    theme: str | None = Query(default=None, max_length=128),
    asset_type: str | None = Query(default=None, pattern="(?i)^(stock|etf)$"),
    sort: Literal["symbol", "name", "price_asc", "price_desc"] = "symbol",
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=512),
):
    supplied = {
        "search": search,
        "region": region,
        "market": market,
        "sector": sector,
        "industry": industry,
        "theme": theme,
        "asset_type": asset_type,
    }
    normalized = {
        key: value.strip().casefold() if value else None for key, value in supplied.items()
    }
    fingerprint = hashlib.sha256(
        json.dumps({**normalized, "sort": sort}, sort_keys=True).encode()
    ).hexdigest()
    secret = env_value(request, "CURSOR_SECRET")
    offset = decode_cursor(cursor, fingerprint, secret)
    clauses = ["a.active = 1"]
    values: list[Any] = []
    for column in ("region", "market", "sector", "industry", "asset_type"):
        if normalized[column]:
            clauses.append(f"LOWER(a.{column}) = ?")
            values.append(normalized[column])
    if normalized["search"]:
        clauses.append("(LOWER(a.symbol) LIKE ? OR LOWER(a.name) LIKE ?)")
        pattern = f"%{normalized['search'].replace('%', '').replace('_', '')}%"
        values.extend([pattern, pattern])
    if normalized["theme"]:
        clauses.append(
            """
            EXISTS (
              SELECT 1 FROM asset_themes at
              JOIN interests i ON i.id = at.interest_id
              WHERE at.asset_id = a.id AND i.active = 1 AND i.kind = 'THEME' AND i.code = ?
            )
            """
        )
        values.append(normalized["theme"])
    where = " AND ".join(clauses)
    total_row = await first(request, f"SELECT COUNT(*) AS total FROM assets a WHERE {where}", *values)
    order = {
        "symbol": "a.symbol, a.id",
        "name": "a.name, a.id",
        "price_asc": "price IS NULL, price ASC, a.symbol, a.id",
        "price_desc": "price IS NULL, price DESC, a.symbol, a.id",
    }[sort]
    data = await rows(
        request,
        f"{ASSET_SUMMARY_SQL} WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
        *values,
        limit,
        offset,
    )
    total = int(total_row.total)
    next_cursor = (
        encode_cursor(offset + len(data), fingerprint, secret)
        if offset + len(data) < total
        else None
    )
    return {
        "data": [asset_summary(row) for row in data],
        "meta": {"data_mode": "demo", "total": total, "next_cursor": next_cursor},
    }


@app.get("/api/v1/assets/{asset_id}/history")
async def get_asset_history(
    asset_id: uuid.UUID,
    request: Request,
    period: Literal["1D", "1M", "1Y", "3Y", "ALL"] = "1Y",
):
    await require_asset(request, str(asset_id))
    return {
        "data": await asset_history(request, str(asset_id), period),
        "meta": {"data_mode": "demo"},
    }


@app.get("/api/v1/assets/{asset_id}")
async def get_asset(asset_id: uuid.UUID, request: Request):
    asset = await require_asset(request, str(asset_id))
    themes = await rows(
        request,
        """
        SELECT i.code, i.title FROM interests i
        JOIN asset_themes at ON at.interest_id = i.id
        WHERE at.asset_id = ? AND i.active = 1 ORDER BY i.title
        """,
        str(asset_id),
    )
    fundamentals = await first(
        request, "SELECT * FROM asset_fundamentals WHERE asset_id = ?", str(asset_id)
    )
    tokens = await rows(
        request,
        "SELECT * FROM tokenized_assets WHERE asset_id = ? AND active = 1 ORDER BY symbol",
        str(asset_id),
    )
    risks = await rows(
        request,
        "SELECT * FROM asset_risks WHERE asset_id = ? AND active = 1 ORDER BY sort_order, id",
        str(asset_id),
    )
    fundamentals_fields = [
        "price", "market_cap", "pe", "eps", "revenue", "revenue_growth",
        "net_income", "debt", "cash_flow", "dividend", "dividend_yield",
    ]
    token_fields = [
        "id", "symbol", "token_name", "issuer", "tokenization_provider", "backing",
        "proof_of_reserves_url", "oracle_provider", "oracle_reference",
        "corporate_actions_info", "availability",
    ]
    detail = {
        **asset_summary(asset),
        "description": asset.description,
        "country": row_value(asset, "country"),
        "themes": [{"code": row.code, "title": row.title} for row in themes],
        "fundamentals": (
            {
                **{field: row_value(fundamentals, field) for field in fundamentals_fields},
                "updated_at": fundamentals.updated_at,
            }
            if fundamentals
            else None
        ),
        "tokens": [
            {field: row_value(token, field) for field in token_fields} for token in tokens
        ],
        "risks": [
            {"id": risk.id, "title": risk.title, "description": risk.description}
            for risk in risks
        ],
        "history": await asset_history(request, str(asset_id), "1Y"),
    }
    return {"data": detail, "meta": {"data_mode": "demo"}}


async def buy_link(request: Request, asset_id: str, token_id: str) -> dict[str, Any]:
    await require_asset(request, asset_id)
    token = await first(
        request,
        "SELECT * FROM tokenized_assets WHERE id = ? AND asset_id = ? AND active = 1",
        token_id,
        asset_id,
    )
    if token is None:
        raise HTTPException(404, "Tokenized representation is unavailable for this asset")
    base_url = env_value(request, "BUY_PROVIDER_BASE_URL").rstrip("/")
    provider = env_value(request, "BUY_PROVIDER_NAME", "YUDY Demo Provider").strip()
    if not base_url.startswith("https://") or not provider:
        raise HTTPException(503, "Demo provider is not configured")
    from urllib.parse import quote

    return {
        "provider": provider,
        "url": f"{base_url}/assets/{quote(token.symbol, safe='')}",
        "external": True,
        "demo": True,
        "tokenized_asset_id": token.id,
        "token_symbol": token.symbol,
    }


@app.get("/api/v1/assets/{asset_id}/buy-link")
async def get_buy_link(
    asset_id: uuid.UUID,
    request: Request,
    tokenized_asset_id: uuid.UUID,
    user: dict[str, str] = Depends(require_consent),
):
    return {
        "data": await buy_link(request, str(asset_id), str(tokenized_asset_id))
    }


@app.post("/api/v1/assets/{asset_id}/buy-click")
async def confirm_buy_click(
    asset_id: uuid.UUID,
    request: Request,
    payload: dict[str, Any],
    user: dict[str, str] = Depends(require_consent),
):
    require_fields(payload, "event_id", "tokenized_asset_id")
    try:
        event_id = str(uuid.UUID(str(payload["event_id"])))
        token_id = str(uuid.UUID(str(payload["tokenized_asset_id"])))
    except ValueError:
        raise HTTPException(422, "Invalid confirmation identifier") from None
    link = await buy_link(request, str(asset_id), token_id)
    existing = await first(request, "SELECT * FROM asset_interactions WHERE id = ?", event_id)
    metadata = json.dumps(
        {"tokenized_asset_id": token_id, "provider": link["provider"], "demo": True},
        separators=(",", ":"),
    )
    if existing is not None:
        existing_meta = json.loads(existing.metadata or "{}")
        if (
            existing.user_id != user["id"]
            or existing.asset_id != str(asset_id)
            or existing.type != "BUY_CLICK"
            or existing_meta.get("tokenized_asset_id") != token_id
        ):
            raise HTTPException(409, "Confirmation ID has already been used")
    else:
        await run(
            request,
            "INSERT INTO asset_interactions (id, user_id, asset_id, type, metadata, created_at) VALUES (?, ?, ?, 'BUY_CLICK', ?, ?)",
            event_id,
            user["id"],
            str(asset_id),
            metadata,
            now(),
        )
        await record_event(
            request,
            "buy_clicked",
            user["id"],
            {"asset_id": str(asset_id), "tokenized_asset_id": token_id, "provider": link["provider"], "demo": True},
        )
    return {"data": link}


def interaction_state(row: Any | None) -> dict[str, bool]:
    return {
        "liked": bool(row and row.liked),
        "disliked": bool(row and row.disliked),
        "saved": bool(row and row.saved),
    }


@app.get("/api/v1/saved")
async def saved_assets(
    request: Request, user: dict[str, str] = Depends(require_consent)
):
    data = await rows(
        request,
        f"""
        {ASSET_SUMMARY_SQL}
        JOIN asset_interaction_states s ON s.asset_id = a.id
        WHERE a.active = 1 AND s.user_id = ? AND s.saved = 1
        ORDER BY a.symbol, a.id
        """,
        user["id"],
    )
    return {"data": [asset_summary(row) for row in data], "meta": {"data_mode": "demo"}}


@app.get("/api/v1/assets/{asset_id}/interactions")
async def get_interaction_state(
    asset_id: uuid.UUID,
    request: Request,
    user: dict[str, str] = Depends(require_consent),
):
    await require_asset(request, str(asset_id))
    state = await first(
        request,
        "SELECT * FROM asset_interaction_states WHERE user_id = ? AND asset_id = ?",
        user["id"],
        str(asset_id),
    )
    return {"data": interaction_state(state)}


@app.post("/api/v1/assets/{asset_id}/{action}")
async def enable_interaction(
    asset_id: uuid.UUID,
    action: Literal["like", "dislike", "save", "view"],
    request: Request,
    user: dict[str, str] = Depends(require_consent),
):
    return {
        "data": await change_interaction(request, user["id"], str(asset_id), action, True)
    }


@app.delete("/api/v1/assets/{asset_id}/{action}")
async def disable_interaction(
    asset_id: uuid.UUID,
    action: Literal["like", "dislike", "save"],
    request: Request,
    user: dict[str, str] = Depends(require_consent),
):
    return {
        "data": await change_interaction(request, user["id"], str(asset_id), action, False)
    }


async def change_interaction(
    request: Request,
    user_id: str,
    asset_id: str,
    action: str,
    active: bool,
) -> dict[str, bool]:
    await require_asset(request, asset_id)
    await run(
        request,
        "INSERT OR IGNORE INTO asset_interaction_states (user_id, asset_id) VALUES (?, ?)",
        user_id,
        asset_id,
    )
    state = await first(
        request,
        "SELECT * FROM asset_interaction_states WHERE user_id = ? AND asset_id = ?",
        user_id,
        asset_id,
    )
    stamp = now()

    async def event(kind: str) -> None:
        await run(
            request,
            "INSERT INTO asset_interactions (id, user_id, asset_id, type, metadata, created_at) VALUES (?, ?, ?, ?, NULL, ?)",
            str(uuid.uuid4()),
            user_id,
            asset_id,
            kind,
            stamp,
        )

    if action == "view":
        await event("VIEW")
        await record_event(request, "asset_viewed", user_id, {"asset_id": asset_id})
    else:
        field, enabled_event, disabled_event = {
            "like": ("liked", "LIKE", "UNLIKE"),
            "dislike": ("disliked", "DISLIKE", "REMOVE_DISLIKE"),
            "save": ("saved", "SAVE", "UNSAVE"),
        }[action]
        current = bool(getattr(state, field))
        if current != active:
            if active and action in {"like", "dislike"}:
                other = "disliked" if action == "like" else "liked"
                if bool(getattr(state, other)):
                    await run(
                        request,
                        f"UPDATE asset_interaction_states SET {other} = 0 WHERE user_id = ? AND asset_id = ?",
                        user_id,
                        asset_id,
                    )
                    await event("REMOVE_DISLIKE" if other == "disliked" else "UNLIKE")
            await run(
                request,
                f"UPDATE asset_interaction_states SET {field} = ? WHERE user_id = ? AND asset_id = ?",
                1 if active else 0,
                user_id,
                asset_id,
            )
            await event(enabled_event if active else disabled_event)
            analytics_name = {
                "like": "asset_liked",
                "dislike": "asset_disliked",
                "save": "asset_saved" if active else "asset_unsaved",
            }[action]
            if active or action == "save":
                await record_event(request, analytics_name, user_id, {"asset_id": asset_id})
    updated = await first(
        request,
        "SELECT * FROM asset_interaction_states WHERE user_id = ? AND asset_id = ?",
        user_id,
        asset_id,
    )
    return interaction_state(updated)


@app.get("/api/v1/learn")
async def learn_articles(request: Request):
    data = await rows(
        request,
        "SELECT id, slug, title, summary, updated_at FROM learn_articles WHERE active = 1 ORDER BY sort_order, slug",
    )
    return {
        "data": [
            {
                "id": row.id,
                "slug": row.slug,
                "title": row.title,
                "summary": row.summary,
                "updated_at": row.updated_at,
            }
            for row in data
        ]
    }


@app.get("/api/v1/learn/{slug}")
async def learn_article(slug: str, request: Request):
    if len(slug) > 128 or any(part == "" for part in slug.split("-")):
        raise HTTPException(422, "Invalid article slug")
    article = await first(
        request,
        "SELECT * FROM learn_articles WHERE slug = ? AND active = 1",
        slug,
    )
    if article is None:
        raise HTTPException(404, "Article is unavailable")
    await record_event(request, "learn_article_opened", properties={"article_id": article.id, "slug": slug})
    return {
        "data": {
            "id": article.id,
            "slug": article.slug,
            "title": article.title,
            "summary": article.summary,
            "content": article.content,
            "updated_at": article.updated_at,
        }
    }


async def selection_choices(
    request: Request, user_id: str, table: str, mapping: str, column: str
) -> list[dict[str, Any]]:
    kind = ", t.kind" if table == "interests" else ""
    data = await rows(
        request,
        f"""
        SELECT t.code, t.title {kind}
        FROM {table} t JOIN {mapping} m ON t.id = m.{column}
        WHERE m.user_id = ? AND t.active = 1 ORDER BY t.code
        """,
        user_id,
    )
    return [
        {
            "code": row.code,
            "title": row.title,
            **({"kind": row.kind} if table == "interests" else {}),
        }
        for row in data
    ]


def xstock_interaction_state(row: Any | None) -> dict[str, bool]:
    return {
        "liked": bool(row and row.liked),
        "disliked": bool(row and row.disliked),
        "saved": bool(row and row.saved),
    }


async def xstock_states(request: Request, user_id: str) -> dict[str, dict[str, bool]]:
    data = await rows(
        request,
        "SELECT * FROM xstock_interaction_states WHERE user_id = ? ORDER BY symbol",
        user_id,
    )
    return {row.xstock_id: xstock_interaction_state(row) for row in data}


async def require_xstock(request: Request, xstock_id: str) -> dict[str, Any]:
    catalog = await official_catalog(request)
    asset = next((item for item in catalog if item["id"] == xstock_id), None)
    if asset is None or asset["trading_halted"]:
        raise HTTPException(404, "xStock is unavailable")
    return asset


def xstock_summary(
    asset: dict[str, Any],
    market: dict[str, Any] | None,
    interaction: dict[str, bool] | None = None,
    reason: str = "Available in the official xStocks catalog for exploration.",
    price: float | None = None,
) -> dict[str, Any]:
    fields = market_fields(market)
    resolved_price = price if price is not None else fields.pop("current_price")
    public_asset = {
        key: value
        for key, value in asset.items()
        if key not in {"solana_mint", "solana_usdc_mint"}
    }
    return {
        **public_asset,
        **fields,
        "price": f"{float(resolved_price):.2f}" if resolved_price is not None else None,
        "as_of": source_timestamp(),
        "reason": reason,
        "interaction": interaction or xstock_interaction_state(None),
    }


@app.get("/api/v1/xstocks")
async def xstock_catalog(
    request: Request,
    search: str | None = Query(default=None, max_length=100),
    asset_type: str | None = Query(default=None, pattern="(?i)^(stock|etf)$"),
    sort: Literal["symbol", "name", "price_asc", "price_desc"] = "symbol",
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
    user: dict[str, str] = Depends(require_consent),
):
    normalized_search = (search or "").strip().casefold()
    normalized_type = (asset_type or "").strip().upper()
    fingerprint = hashlib.sha256(
        json.dumps(
            {"search": normalized_search, "asset_type": normalized_type, "sort": sort},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    offset = decode_cursor(cursor, fingerprint, env_value(request, "CURSOR_SECRET"))
    catalog, markets, states = await asyncio.gather(
        official_catalog(request),
        coingecko_markets(request),
        xstock_states(request, user["id"]),
    )
    filtered = [item for item in catalog if not item["trading_halted"]]
    if normalized_search:
        filtered = [
            item
            for item in filtered
            if normalized_search
            in " ".join(
                (item["symbol"], item["name"], item["underlying_symbol"])
            ).casefold()
        ]
    if normalized_type:
        filtered = [item for item in filtered if item["asset_type"] == normalized_type]

    def price_value(item: dict[str, Any]) -> float | None:
        value = market_fields(markets.get(item["symbol"].casefold()))["current_price"]
        return float(value) if value is not None else None

    if sort == "name":
        filtered.sort(key=lambda item: (item["name"].casefold(), item["id"]))
    elif sort in {"price_asc", "price_desc"}:
        reverse = sort == "price_desc"
        filtered.sort(
            key=lambda item: (
                price_value(item) is None,
                -(price_value(item) or 0.0) if reverse else (price_value(item) or 0.0),
                item["symbol"],
            )
        )
    else:
        filtered.sort(key=lambda item: (item["symbol"], item["id"]))
    page = filtered[offset : offset + limit]
    next_cursor = (
        encode_cursor(offset + len(page), fingerprint, env_value(request, "CURSOR_SECRET"))
        if offset + len(page) < len(filtered)
        else None
    )
    return {
        "data": [
            xstock_summary(
                item,
                markets.get(item["symbol"].casefold()),
                states.get(item["id"]),
            )
            for item in page
        ],
        "meta": {
            "data_mode": "live_xstocks",
            "total": len(filtered),
            "next_cursor": next_cursor,
        },
    }


@app.get("/api/v1/xstocks/saved")
async def saved_xstocks(
    request: Request,
    user: dict[str, str] = Depends(require_consent),
):
    catalog, markets, states = await asyncio.gather(
        official_catalog(request),
        coingecko_markets(request),
        xstock_states(request, user["id"]),
    )
    saved = [
        item
        for item in catalog
        if not item["trading_halted"] and states.get(item["id"], {}).get("saved")
    ]
    saved.sort(key=lambda item: item["symbol"])
    return {
        "data": [
            xstock_summary(
                item,
                markets.get(item["symbol"].casefold()),
                states[item["id"]],
                "Saved for later exploration.",
            )
            for item in saved
        ],
        "meta": {"data_mode": "live_xstocks", "total": len(saved)},
    }


@app.get("/api/v1/xstocks/{xstock_id}/venues")
async def xstock_venues(
    xstock_id: str,
    request: Request,
    user: dict[str, str] = Depends(require_consent),
):
    asset = await require_xstock(request, xstock_id)
    venues = [
        {
            "name": "Kraken",
            "kind": "CEX",
            "url": f"https://www.kraken.com/xstocks/{asset['symbol'].casefold()}",
            "network": None,
        }
    ]
    if asset.get("solana_mint") and asset.get("solana_usdc_mint"):
        venues.append(
            {
                "name": "Jupiter",
                "kind": "DEX",
                "url": "https://jup.ag/?"
                + urlencode(
                    {
                        "buy": asset["solana_mint"],
                        "sell": asset["solana_usdc_mint"],
                    }
                ),
                "network": "Solana",
            }
        )
    return {"data": venues, "meta": {"external": True}}


@app.post("/api/v1/xstocks/{xstock_id}/buy-click", status_code=204)
async def xstock_buy_click(
    xstock_id: str,
    request: Request,
    payload: dict[str, Any],
    user: dict[str, str] = Depends(require_consent),
):
    asset = await require_xstock(request, xstock_id)
    venue = str(payload.get("venue") or "")
    if venue not in {"Kraken", "Jupiter"}:
        raise HTTPException(422, "Unknown external venue")
    stamp = now()
    await run(
        request,
        "INSERT INTO xstock_interactions (id, user_id, xstock_id, symbol, type, metadata, created_at) "
        "VALUES (?, ?, ?, ?, 'BUY_CLICK', ?, ?)",
        str(uuid.uuid4()),
        user["id"],
        asset["id"],
        asset["symbol"],
        json.dumps({"venue": venue}, separators=(",", ":")),
        stamp,
    )
    await record_event(
        request,
        "xstock_buy_clicked",
        user["id"],
        {"xstock_id": asset["id"], "symbol": asset["symbol"], "venue": venue},
    )
    return Response(status_code=204)


async def change_xstock_interaction(
    request: Request,
    user_id: str,
    xstock_id: str,
    action: str,
    active: bool,
) -> dict[str, bool]:
    asset = await require_xstock(request, xstock_id)
    stamp = now()
    await run(
        request,
        "INSERT OR IGNORE INTO xstock_interaction_states "
        "(user_id, xstock_id, symbol, updated_at) VALUES (?, ?, ?, ?)",
        user_id,
        asset["id"],
        asset["symbol"],
        stamp,
    )
    state = await first(
        request,
        "SELECT * FROM xstock_interaction_states WHERE user_id = ? AND xstock_id = ?",
        user_id,
        asset["id"],
    )

    async def event(kind: str) -> None:
        await run(
            request,
            "INSERT INTO xstock_interactions (id, user_id, xstock_id, symbol, type, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, NULL, ?)",
            str(uuid.uuid4()),
            user_id,
            asset["id"],
            asset["symbol"],
            kind,
            stamp,
        )

    field, enabled_event, disabled_event = {
        "like": ("liked", "LIKE", "UNLIKE"),
        "dislike": ("disliked", "DISLIKE", "REMOVE_DISLIKE"),
        "save": ("saved", "SAVE", "UNSAVE"),
    }[action]
    if bool(getattr(state, field)) != active:
        if active and action in {"like", "dislike"}:
            other = "disliked" if action == "like" else "liked"
            if bool(getattr(state, other)):
                await run(
                    request,
                    f"UPDATE xstock_interaction_states SET {other} = 0 WHERE user_id = ? AND xstock_id = ?",
                    user_id,
                    asset["id"],
                )
                await event("REMOVE_DISLIKE" if other == "disliked" else "UNLIKE")
        await run(
            request,
            f"UPDATE xstock_interaction_states SET {field} = ?, updated_at = ? "
            "WHERE user_id = ? AND xstock_id = ?",
            1 if active else 0,
            stamp,
            user_id,
            asset["id"],
        )
        await event(enabled_event if active else disabled_event)
        await record_event(
            request,
            f"xstock_{enabled_event.lower() if active else disabled_event.lower()}",
            user_id,
            {"xstock_id": asset["id"], "symbol": asset["symbol"]},
        )
    updated = await first(
        request,
        "SELECT * FROM xstock_interaction_states WHERE user_id = ? AND xstock_id = ?",
        user_id,
        asset["id"],
    )
    return xstock_interaction_state(updated)


@app.post("/api/v1/xstocks/{xstock_id}/{action}")
async def enable_xstock_interaction(
    xstock_id: str,
    action: Literal["like", "dislike", "save"],
    request: Request,
    user: dict[str, str] = Depends(require_consent),
):
    return {
        "data": await change_xstock_interaction(
            request, user["id"], xstock_id, action, True
        )
    }


@app.delete("/api/v1/xstocks/{xstock_id}/{action}")
async def disable_xstock_interaction(
    xstock_id: str,
    action: Literal["like", "dislike", "save"],
    request: Request,
    user: dict[str, str] = Depends(require_consent),
):
    return {
        "data": await change_xstock_interaction(
            request, user["id"], xstock_id, action, False
        )
    }


@app.get("/api/v1/selection/xstocks")
async def xstocks_for_you(
    request: Request,
    limit: int = Query(default=8, ge=4, le=12),
    user: dict[str, str] = Depends(require_consent),
):
    profile = await first(request, "SELECT * FROM user_profiles WHERE user_id = ?", user["id"])
    risk = await first(request, "SELECT * FROM risk_profiles WHERE user_id = ?", user["id"])
    questionnaire = await current_questionnaire(request)
    if (
        profile is None
        or not bool(profile.onboarding_completed)
        or risk is None
        or risk.questionnaire_version != questionnaire.version
    ):
        raise HTTPException(409, "Complete onboarding and the current risk questionnaire first")
    score = int(risk.risk_score)
    signals = {
        "experience": profile.experience,
        "investment_horizon": profile.investment_horizon,
        "risk_category": risk.risk_category,
        "risk_score_band": f"{(score // 10) * 10}-{min(100, (score // 10) * 10 + 9)}",
        "interests": await selection_choices(request, user["id"], "interests", "user_interests", "interest_id"),
        "excluded": await selection_choices(request, user["id"], "interests", "user_excluded_interests", "interest_id"),
        "goals": await selection_choices(request, user["id"], "goals", "user_goals", "goal_id"),
        "regions": await selection_choices(request, user["id"], "regions", "user_regions", "region_id"),
    }
    catalog, markets, states = await asyncio.gather(
        official_catalog(request),
        coingecko_markets(request),
        xstock_states(request, user["id"]),
    )
    signals.update(
        {
            "liked_assets": [
                item["symbol"] for item in catalog if states.get(item["id"], {}).get("liked")
            ],
            "saved_assets": [
                item["symbol"] for item in catalog if states.get(item["id"], {}).get("saved")
            ],
            "disliked_assets": [
                item["symbol"] for item in catalog if states.get(item["id"], {}).get("disliked")
            ],
        }
    )
    charted_catalog = [
        item
        for item in catalog
        if not states.get(item["id"], {}).get("disliked")
        and len(market_fields(markets.get(item["symbol"].casefold()))["sparkline_7d"]) > 1
    ]
    selection_limit = min(limit, len(charted_catalog))
    chosen = (
        await ai_selection(request, signals, charted_catalog, selection_limit)
        if selection_limit
        else []
    )
    by_symbol = {item["symbol"]: item for item in charted_catalog}
    prices = await asyncio.gather(*(quote(request, item["symbol"]) for item in chosen))
    as_of = source_timestamp()
    data = []
    for item, price in zip(chosen, prices):
        asset = by_symbol[item["symbol"]]
        data.append(xstock_summary(
            asset,
            markets.get(item["symbol"].casefold()),
            states.get(asset["id"]),
            item["reason"],
            price,
        ))
    await record_event(
        request,
        "ai_xstocks_selection_generated",
        user["id"],
        {"count": len(data), "model": env_value(request, "AI_MODEL")},
    )
    return {
        "data": data,
        "meta": {
            "data_mode": "live_xstocks",
            "source": "https://api.xstocks.fi/api/v2/public/assets",
            "generated_at": as_of,
            "privacy": {
                "sent_to_ai": list(AI_PROFILE_FIELDS),
                "never_sent": list(AI_EXCLUDED_FIELDS),
            },
        },
    }


def similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    matches = [
        bool(left.get(key) and left.get(key) == right.get(key))
        for key in ("sector", "industry", "region", "country", "asset_type")
    ]
    matches.append(bool(set(left["themes"]) & set(right["themes"])))
    return sum(matches) / len(matches)


@app.get("/api/v1/selection/for-you")
async def for_you(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=512),
    user: dict[str, str] = Depends(require_consent),
):
    profile = await first(request, "SELECT * FROM user_profiles WHERE user_id = ?", user["id"])
    risk = await first(request, "SELECT * FROM risk_profiles WHERE user_id = ?", user["id"])
    questionnaire = await current_questionnaire(request)
    if (
        profile is None
        or not bool(profile.onboarding_completed)
        or risk is None
        or risk.questionnaire_version != questionnaire.version
    ):
        raise HTTPException(409, "Complete onboarding and the current risk questionnaire first")

    states_data = await rows(
        request,
        "SELECT * FROM asset_interaction_states WHERE user_id = ? ORDER BY asset_id",
        user["id"],
    )
    states = {row.asset_id: interaction_state(row) for row in states_data}
    viewed_rows = await rows(
        request,
        "SELECT DISTINCT asset_id FROM asset_interactions WHERE user_id = ? AND type = 'VIEW' ORDER BY asset_id",
        user["id"],
    )
    signals = {
        "experience": profile.experience,
        "horizon": profile.investment_horizon,
        "risk": risk.risk_category,
        "interests": await selection_choices(request, user["id"], "interests", "user_interests", "interest_id"),
        "excluded": await selection_choices(request, user["id"], "interests", "user_excluded_interests", "interest_id"),
        "goals": await selection_choices(request, user["id"], "goals", "user_goals", "goal_id"),
        "regions": await selection_choices(request, user["id"], "regions", "user_regions", "region_id"),
        "states": states,
        "viewed": [row.asset_id for row in viewed_rows],
    }
    asset_rows = await rows(
        request,
        f"{ASSET_SUMMARY_SQL} WHERE a.active = 1 ORDER BY a.symbol, a.id",
    )
    theme_rows = await rows(
        request,
        """
        SELECT at.asset_id, i.code FROM asset_themes at
        JOIN interests i ON i.id = at.interest_id
        WHERE i.active = 1 ORDER BY i.code
        """,
    )
    themes: dict[str, list[str]] = {}
    for row in theme_rows:
        themes.setdefault(row.asset_id, []).append(row.code)
    candidates = [
        {
            "id": row.id,
            "symbol": row.symbol,
            "sector": row_value(row, "sector"),
            "industry": row_value(row, "industry"),
            "region": row_value(row, "region"),
            "country": row_value(row, "country"),
            "asset_type": row.asset_type,
            "themes": themes.get(row.id, []),
            "has_dividend": bool(row.has_dividend),
            "summary": asset_summary(row),
        }
        for row in asset_rows
    ]
    weights = json.loads(env_value(request, "PERSONALIZATION_WEIGHTS"))
    required_weights = {
        "sector_match", "theme_match", "region_match", "goal_match", "experience_match",
        "horizon_match", "risk_match", "liked_asset", "saved_asset", "liked_similar",
        "saved_similar", "viewed_similar", "excluded_interest", "disliked_asset",
        "disliked_similar", "sector_codes", "goal_themes", "etf_goals", "etf_experience",
        "etf_horizons", "etf_risk_categories",
    }
    if not required_weights <= set(weights):
        raise HTTPException(503, "Personalization weights are incomplete")
    by_id = {candidate["id"]: candidate for candidate in candidates}
    ranked: list[dict[str, Any]] = []
    for asset in candidates:
        contributions: list[tuple[float, dict[str, str]]] = []

        def add(value: float, kind: str, text: str) -> None:
            if value:
                contributions.append((value, {"type": kind, "text": text}))

        def matches(interest: dict[str, Any]) -> bool:
            if interest["kind"] == "THEME":
                return interest["code"] in asset["themes"]
            sector_code = weights["sector_codes"].get(
                interest["code"], interest["code"].replace("_", " ")
            )
            return sector_code.casefold() == (asset["sector"] or "").casefold()

        for interest in signals["interests"]:
            if matches(interest):
                add(
                    weights["theme_match"] if interest["kind"] == "THEME" else weights["sector_match"],
                    "interest_match",
                    f"You selected {interest['title']} as an interest.",
                )
        for interest in signals["excluded"]:
            if matches(interest):
                add(weights["excluded_interest"], "excluded_interest", f"Shown lower because you excluded {interest['title']}.")
        for region_item in signals["regions"]:
            if region_item["code"] == asset["region"]:
                add(weights["region_match"], "region_match", f"You selected {region_item['title']} as a region to explore.")
        for goal in signals["goals"]:
            related = (
                (asset["asset_type"] == "ETF" and goal["code"] in weights["etf_goals"])
                or bool(set(asset["themes"]) & set(weights["goal_themes"].get(goal["code"], [])))
                or (goal["code"] == "income" and asset["has_dividend"])
            )
            if related:
                add(weights["goal_match"], "goal_match", f"This demo example relates to your {goal['title']} exploration goal.")
        if asset["asset_type"] == "ETF":
            for field, values, weight_name, kind in (
                ("experience", weights["etf_experience"], "experience_match", "experience"),
                ("horizon", weights["etf_horizons"], "horizon_match", "horizon"),
                ("risk", weights["etf_risk_categories"], "risk_match", "risk_profile"),
            ):
                if signals[field] in values:
                    add(weights[weight_name], kind, f"ETF example included using your {kind.replace('_', ' ')} response; this is for exploration.")
        for field, direct_key, related_key, kind, label in (
            ("liked", "liked_asset", "liked_similar", "like", "liked"),
            ("saved", "saved_asset", "saved_similar", "save", "saved"),
            ("disliked", "disliked_asset", "disliked_similar", "dislike", "marked not interested"),
        ):
            sources = [by_id[item_id] for item_id, state in states.items() if state[field] and item_id in by_id]
            if any(source["id"] == asset["id"] for source in sources):
                add(weights[direct_key], kind, f"You {label} this asset.")
            others = [source for source in sources if source["id"] != asset["id"]]
            strength = max((similarity(asset, source) for source in others), default=0)
            add(weights[related_key] * strength, f"{kind}_similar", f"Shares metadata with an asset you {label}.")
        viewed = [by_id[item_id] for item_id in signals["viewed"] if item_id in by_id]
        strength = max((similarity(asset, source) for source in viewed), default=0)
        add(weights["viewed_similar"] * strength, "view_similar", "Shares metadata with an asset you opened.")
        reasons = [reason for _, reason in sorted(contributions, key=lambda item: -abs(item[0]))[:3]]
        if not reasons:
            reasons = [{"type": "catalog", "text": "An active demo catalog example; no matching personal signal yet."}]
        ranked.append({"asset": asset, "score": sum(value for value, _ in contributions), "reasons": reasons})
    ranked.sort(key=lambda item: (-item["score"], item["asset"]["symbol"], item["asset"]["id"]))
    fingerprint = hashlib.sha256(
        json.dumps([user["id"], signals, [item["asset"]["id"] for item in ranked], weights], sort_keys=True).encode()
    ).hexdigest()
    secret = env_value(request, "CURSOR_SECRET")
    offset = decode_cursor(cursor, fingerprint, secret)
    page = ranked[offset : offset + limit]
    next_cursor = encode_cursor(offset + len(page), fingerprint, secret) if offset + len(page) < len(ranked) else None
    return {
        "data": [
            {
                "asset": item["asset"]["summary"],
                "interaction": states.get(item["asset"]["id"], {"liked": False, "disliked": False, "saved": False}),
                "reasons": item["reasons"],
            }
            for item in page
        ],
        "meta": {"data_mode": "demo", "total": len(ranked), "next_cursor": next_cursor},
    }


Default = asgi.entrypoint(app)
