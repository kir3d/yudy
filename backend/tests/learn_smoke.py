"""Read-only Learn HTTP smoke against local PostgreSQL."""
import os

import httpx

BASE_URL = os.environ.get("LEARN_SMOKE_URL", "http://localhost:8000") + "/api/v1/learn/articles"


def main():
    response = httpx.get(BASE_URL, timeout=20)
    assert response.status_code == 200
    articles = response.json()["data"]
    assert len(articles) == len({a["slug"] for a in articles}) == 8
    for article in articles:
        assert "content" not in article
        response = httpx.get(BASE_URL + "/" + article["slug"], timeout=20)
        assert response.status_code == 200
        detail = response.json()["data"]
        assert detail["id"] == article["id"] and detail["content"] and detail["updated_at"]
    assert httpx.get(BASE_URL + "/missing", timeout=20).status_code == 404
    assert httpx.get(BASE_URL + "/invalid_slug", timeout=20).status_code == 422
    print("PASS: all eight public Learn articles, full content and unavailable/invalid slug errors")


if __name__ == "__main__":
    main()
