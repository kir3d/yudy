"""Explicit HTTP smoke against local PostgreSQL/Redis; no credentials printed."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

BASE_URL = os.environ.get("RISK_SMOKE_URL", "http://localhost:8000") + "/api/v1"


def request(method, path, **kwargs):
    return httpx.request(method, BASE_URL + path, timeout=20, **kwargs)


def main():
    sessions = []
    try:
        for _ in range(2):
            response = request(
                "POST",
                "/auth/register",
                json={
                    "email": f"risk-smoke-{uuid.uuid4().hex}@example.com",
                    "password": "Local-risk-password-42",
                },
            )
            assert response.status_code == 201
            sessions.append(response.json()["data"])
        headers = [{"Authorization": "Bearer " + session["access_token"]} for session in sessions]
        assert request("GET", "/risk/questions", headers=headers[0]).status_code == 403
        documents = request("GET", "/legal/documents").json()["data"]
        goal_id = request("GET", "/goals").json()["data"][0]["id"]
        for header in headers:
            response = request(
                "POST",
                "/legal/consents",
                headers=header,
                json={
                    "consents": [
                        {"document_id": doc["id"], "version": doc["version"], "accepted": True}
                        for doc in documents
                    ]
                },
            )
            assert response.status_code == 200
            assert request("GET", "/risk/questions", headers=header).status_code == 403
            response = request(
                "POST",
                "/profile/onboarding",
                headers=header,
                json={
                    "experience": "NEW",
                    "investment_horizon": "FIVE_PLUS",
                    "goal_ids": [goal_id],
                },
            )
            assert response.status_code == 200
        questionnaire = request("GET", "/risk/questions", headers=headers[0]).json()["data"]
        questions = questionnaire["questions"]
        assert len(questions) == 7
        assert all(
            "score" not in option for question in questions for option in question["options"]
        )
        assert request("GET", "/risk/profile", headers=headers[0]).status_code == 404

        def body(choice):
            return {
                "questionnaire_version": questionnaire["questionnaire_version"],
                "answers": [
                    {"question_id": question["id"], "option_id": question["options"][choice]["id"]}
                    for question in questions
                ],
            }

        for choice, category, score in ((0, "Conservative", 0), (3, "Growth", 100)):
            response = request("POST", "/risk/assessment", headers=headers[0], json=body(choice))
            assert response.status_code == 200
            assert response.json()["data"]["risk_category"] == category
            assert response.json()["data"]["risk_score"] == score
            assert request("GET", "/risk/profile", headers=headers[0]).json() == response.json()
        balanced = body(1)
        for index in range(3):
            balanced["answers"][index]["option_id"] = questions[index]["options"][2]["id"]
        response = request("POST", "/risk/assessment", headers=headers[0], json=balanced)
        assert response.status_code == 200
        assert response.json()["data"]["risk_category"] == "Balanced"
        assert response.json()["data"]["risk_score"] == 48
        saved = request("GET", "/risk/profile", headers=headers[0]).json()
        invalid = body(3)
        invalid["answers"][0]["option_id"] = questions[1]["options"][0]["id"]
        assert (
            request("POST", "/risk/assessment", headers=headers[0], json=invalid).status_code == 422
        )
        assert request("GET", "/risk/profile", headers=headers[0]).json() == saved
        stale = {**body(0), "questionnaire_version": "stale-test-version"}
        assert (
            request("POST", "/risk/assessment", headers=headers[0], json=stale).status_code == 409
        )
        assert request("GET", "/risk/profile", headers=headers[1]).status_code == 404
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(
                    lambda choice: request(
                        "POST", "/risk/assessment", headers=headers[0], json=body(choice)
                    ),
                    (0, 3),
                )
            )
        assert all(response.status_code == 200 for response in responses)
        result = request("GET", "/risk/profile", headers=headers[0]).json()["data"]
        assert (result["risk_score"], result["risk_category"]) in {
            (0, "Conservative"),
            (100, "Growth"),
        }
        print(
            "PASS: risk prerequisites, all categories, persistence, isolation, "
            "stale/invalid input and concurrent assessment on PostgreSQL"
        )
    finally:
        for session in sessions:
            assert (
                request(
                    "POST", "/auth/logout", json={"refresh_token": session["refresh_token"]}
                ).status_code
                == 204
            )


if __name__ == "__main__":
    main()
