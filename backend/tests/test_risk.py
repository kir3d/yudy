import json
import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.models.risk import RiskAnswerOption, RiskProfile, RiskQuestion, RiskQuestionnaire
from app.services.risk import categorize, normalize_score
from app.services.risk_seed import seed_risk_questionnaire


def account(client, email="risk@example.com", consent=True, onboarding=True):
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "risk-password-42"}
    )
    assert response.status_code == 201
    headers = {"Authorization": "Bearer " + response.json()["data"]["access_token"]}
    if consent:
        documents = client.get("/api/v1/legal/documents").json()["data"]
        response = client.post(
            "/api/v1/legal/consents",
            headers=headers,
            json={
                "consents": [
                    {"document_id": doc["id"], "version": doc["version"], "accepted": True}
                    for doc in documents
                ]
            },
        )
        assert response.status_code == 200
    if onboarding:
        goal = client.get("/api/v1/goals").json()["data"][0]["id"]
        response = client.post(
            "/api/v1/profile/onboarding",
            headers=headers,
            json={"experience": "NEW", "investment_horizon": "FIVE_PLUS", "goal_ids": [goal]},
        )
        assert response.status_code == 200
    return headers


def questionnaire(client, headers):
    response = client.get("/api/v1/risk/questions", headers=headers)
    assert response.status_code == 200
    return response.json()["data"]


def answers(questions, choice=0):
    return {
        "questionnaire_version": questions["questionnaire_version"],
        "answers": [
            {"question_id": question["id"], "option_id": question["options"][choice]["id"]}
            for question in questions["questions"]
        ],
    }


@pytest.mark.parametrize(
    "score,category",
    [
        (0, "Conservative"),
        (33, "Conservative"),
        (34, "Balanced"),
        (66, "Balanced"),
        (67, "Growth"),
        (100, "Growth"),
    ],
)
def test_category_boundaries(score, category):
    assert categorize(score, 33, 66) == category


def test_normalization_uses_round_half_up_and_configurable_thresholds():
    assert normalize_score(0, 21) == 0
    assert normalize_score(7, 21) == 33
    assert normalize_score(14, 21) == 67
    assert normalize_score(21, 21) == 100
    assert normalize_score(1, 8) == 13
    assert categorize(40, 40, 80) == "Conservative"
    assert categorize(41, 40, 80) == "Balanced"
    with pytest.raises(ValueError):
        normalize_score(1, 0)
    with pytest.raises(ValueError):
        categorize(101, 33, 66)


def test_risk_routes_require_auth_consent_and_completed_onboarding(client):
    first = account(client, consent=False, onboarding=False)
    second = account(client, email="not-onboarded@example.com", onboarding=False)
    fake_payload = {
        "questionnaire_version": "test",
        "answers": [{"question_id": str(uuid.uuid4()), "option_id": str(uuid.uuid4())}],
    }
    for method, path in (("get", "/questions"), ("get", "/profile"), ("post", "/assessment")):
        kwargs = {"json": fake_payload} if method == "post" else {}
        for headers in (first, second):
            assert (
                getattr(client, method)(
                    "/api/v1/risk" + path, headers=headers, **kwargs
                ).status_code
                == 403
            )
        assert getattr(client, method)("/api/v1/risk" + path, **kwargs).status_code == 401


def test_questions_cover_all_dimensions_without_exposing_scoring(client):
    headers = account(client)
    questions = questionnaire(client, headers)
    assert {question["code"] for question in questions["questions"]} == {
        "experience",
        "horizon",
        "loss_reaction",
        "volatility",
        "preservation_growth",
        "drawdown",
        "uncertainty",
    }
    assert [question["sort_order"] for question in questions["questions"]] == list(range(7))
    for question in questions["questions"]:
        assert len(question["options"]) == 4
        assert all("score" not in option for option in question["options"])
    assert "conservative_max" not in questions
    assert client.get("/api/v1/risk/profile", headers=headers).status_code == 404


@pytest.mark.parametrize(
    "choice,score,category",
    [(0, 0, "Conservative"), (1, 33, "Conservative"), (2, 67, "Growth"), (3, 100, "Growth")],
)
def test_assessment_persists_server_scoring(client, choice, score, category):
    headers = account(client)
    questions = questionnaire(client, headers)
    payload = answers(questions, choice)
    response = client.post("/api/v1/risk/assessment", headers=headers, json=payload)
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["risk_score"] == score
    assert result["risk_category"] == category
    assert result["questionnaire_version"] == questions["questionnaire_version"]
    assert result["is_current"] and result["calculated_at"]
    loaded = client.get("/api/v1/risk/profile", headers=headers).json()["data"]
    # SQLite strips timezone metadata; compare the persisted timestamp value separately.
    assert loaded["calculated_at"].rstrip("Z") == result["calculated_at"].rstrip("Z")
    assert {key: value for key, value in loaded.items() if key != "calculated_at"} == {
        key: value for key, value in result.items() if key != "calculated_at"
    }

    async def stored():
        async with client.db_factory() as session:
            row = await session.scalar(select(RiskProfile))
            assert row.answers == payload["answers"]

    client.portal.call(stored)


def test_balanced_result_reassessment_and_user_isolation(client):
    first = account(client)
    second = account(client, "second-risk@example.com")
    questions = questionnaire(client, first)
    payload = answers(questions, 1)
    for i in range(3):
        payload["answers"][i]["option_id"] = questions["questions"][i]["options"][2]["id"]
    response = client.post("/api/v1/risk/assessment", headers=first, json=payload)
    assert response.json()["data"]["risk_category"] == "Balanced"
    assert response.json()["data"]["risk_score"] == 48
    assert client.get("/api/v1/risk/profile", headers=second).status_code == 404
    response = client.post("/api/v1/risk/assessment", headers=first, json=answers(questions, 3))
    assert response.json()["data"]["risk_category"] == "Growth"
    assert client.get("/api/v1/risk/profile", headers=first).json()["data"]["risk_score"] == 100

    async def count():
        async with client.db_factory() as session:
            assert await session.scalar(select(func.count()).select_from(RiskProfile)) == 1

    client.portal.call(count)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "unknown_question",
        "unknown_option",
        "wrong_question",
        "stale",
        "empty",
        "score",
        "user_id",
    ],
)
def test_invalid_assessment_preserves_previous_result(client, change):
    headers = account(client)
    questions = questionnaire(client, headers)
    before = client.post("/api/v1/risk/assessment", headers=headers, json=answers(questions, 0))
    assert before.status_code == 200
    saved = client.get("/api/v1/risk/profile", headers=headers).json()
    payload = answers(questions, 3)
    if change == "missing":
        payload["answers"].pop()
    elif change == "duplicate":
        payload["answers"].append(payload["answers"][0])
    elif change == "unknown_question":
        payload["answers"][0]["question_id"] = str(uuid.uuid4())
    elif change == "unknown_option":
        payload["answers"][0]["option_id"] = str(uuid.uuid4())
    elif change == "wrong_question":
        payload["answers"][0]["option_id"] = payload["answers"][1]["option_id"]
    elif change == "stale":
        payload["questionnaire_version"] = "old-version"
    elif change == "empty":
        payload["answers"] = []
    elif change == "score":
        payload["answers"][0]["score"] = 100
    else:
        payload["user_id"] = str(uuid.uuid4())
    response = client.post("/api/v1/risk/assessment", headers=headers, json=payload)
    assert response.status_code == (409 if change == "stale" else 422)
    assert client.get("/api/v1/risk/profile", headers=headers).json() == saved


def test_new_version_keeps_old_result_and_rejects_previous_answer_ids(client, tmp_path):
    headers = account(client)
    old_questions = questionnaire(client, headers)
    old_answers = answers(old_questions, 1)
    assert (
        client.post("/api/v1/risk/assessment", headers=headers, json=old_answers).status_code == 200
    )
    manifest = json.loads(Settings().risk_questionnaire_path.read_text())
    manifest["version"] = "risk-test-v2"
    manifest["conservative_max"] = 40
    path = tmp_path / "risk.json"
    path.write_text(json.dumps(manifest))

    async def publish():
        async with client.db_factory() as session:
            await seed_risk_questionnaire(session, path)

    client.portal.call(publish)
    profile = client.get("/api/v1/risk/profile", headers=headers).json()["data"]
    assert not profile["is_current"]
    assert profile["questionnaire_version"] == old_questions["questionnaire_version"]
    assert (
        client.post("/api/v1/risk/assessment", headers=headers, json=old_answers).status_code == 409
    )
    old_answers["questionnaire_version"] = manifest["version"]
    assert (
        client.post("/api/v1/risk/assessment", headers=headers, json=old_answers).status_code == 422
    )
    new_questions = questionnaire(client, headers)
    response = client.post(
        "/api/v1/risk/assessment", headers=headers, json=answers(new_questions, 2)
    )
    assert response.status_code == 200 and response.json()["data"]["is_current"]

    async def counts():
        async with client.db_factory() as session:
            assert await session.scalar(select(func.count()).select_from(RiskQuestionnaire)) == 2
            assert await session.scalar(select(func.count()).select_from(RiskQuestion)) == 14
            assert await session.scalar(select(func.count()).select_from(RiskAnswerOption)) == 56

    client.portal.call(counts)


def test_seed_idempotency_and_published_version_immutability(client, tmp_path):
    manifest = json.loads(Settings().risk_questionnaire_path.read_text())
    manifest["questions"][0]["options"][0]["text"] = "Changed text"
    path = tmp_path / "risk.json"
    path.write_text(json.dumps(manifest))

    async def check():
        async with client.db_factory() as session:
            await seed_risk_questionnaire(session, Settings().risk_questionnaire_path)
            assert await session.scalar(select(func.count()).select_from(RiskQuestionnaire)) == 1
        async with client.db_factory() as session:
            with pytest.raises(ValueError, match="immutable"):
                await seed_risk_questionnaire(session, path)

    client.portal.call(check)
    headers = account(client)
    assert len(questionnaire(client, headers)["questions"]) == 7


@pytest.mark.parametrize("change", ["thresholds", "duplicate", "zero_scores"])
def test_invalid_seed_is_rejected_before_publishing(client, tmp_path, change):
    manifest = json.loads(Settings().risk_questionnaire_path.read_text())
    manifest["version"] = "invalid-seed"
    if change == "thresholds":
        manifest["conservative_max"] = manifest["balanced_max"]
    elif change == "duplicate":
        manifest["questions"].append(manifest["questions"][0])
    else:
        for option in manifest["questions"][0]["options"]:
            option["score"] = 0
    path = tmp_path / "risk.json"
    path.write_text(json.dumps(manifest))

    async def check():
        async with client.db_factory() as session:
            with pytest.raises(ValueError):
                await seed_risk_questionnaire(session, path)
        async with client.db_factory() as session:
            assert await session.scalar(select(func.count()).select_from(RiskQuestionnaire)) == 1

    client.portal.call(check)
