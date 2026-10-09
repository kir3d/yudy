import json

import pytest
from sqlalchemy import select, update

from app.core.config import Settings
from app.models.learn import LearnArticle
from app.services.learn_seed import seed_articles


@pytest.fixture
def learn(client):
    async def seed():
        async with client.db_factory() as session:
            await seed_articles(session, Settings().learn_articles_path)

    client.portal.call(seed)
    return client


def test_public_list_and_all_detail_topics(learn):
    items = learn.get("/api/v1/learn/articles").json()["data"]
    assert len(items) == len({a["slug"] for a in items}) == 8
    assert items[0]["slug"] == "tokenized-stocks"
    assert all("content" not in a and a["updated_at"] for a in items)
    for item in items:
        response = learn.get("/api/v1/learn/articles/" + item["slug"])
        assert response.status_code == 200
        detail = response.json()["data"]
        assert detail["id"] == item["id"] and detail["content"]
    assert learn.get("/api/v1/learn/articles/missing").status_code == 404
    assert learn.get("/api/v1/learn/articles/Invalid_slug").status_code == 422


def test_inactive_article_unavailable_but_record_preserved(learn):
    item = learn.get("/api/v1/learn/articles").json()["data"][0]

    async def deactivate():
        async with learn.db_factory() as session:
            await session.execute(
                update(LearnArticle).where(LearnArticle.slug == item["slug"]).values(active=False)
            )
            await session.commit()

    learn.portal.call(deactivate)
    assert len(learn.get("/api/v1/learn/articles").json()["data"]) == 7
    assert learn.get("/api/v1/learn/articles/" + item["slug"]).status_code == 404


def test_seed_idempotent_updates_content_preserving_identity(learn, tmp_path):
    before = learn.get("/api/v1/learn/articles/tokenized-stocks").json()["data"]
    data = json.loads(Settings().learn_articles_path.read_text())
    data["articles"][0]["content"] += "\n\nUpdated editorial text."
    path = tmp_path / "learn.json"
    path.write_text(json.dumps(data))

    async def seed(p):
        async with learn.db_factory() as session:
            await seed_articles(session, p)

    learn.portal.call(seed, Settings().learn_articles_path)
    assert learn.get("/api/v1/learn/articles/tokenized-stocks").json()["data"] == before
    learn.portal.call(seed, path)
    after = learn.get("/api/v1/learn/articles/tokenized-stocks").json()["data"]
    assert after["id"] == before["id"] and after["content"] != before["content"]
    assert after["updated_at"] != before["updated_at"]


@pytest.mark.parametrize("change", ["duplicate", "invalid_slug", "missing_content", "empty"])
def test_invalid_manifest_has_no_partial_writes(learn, tmp_path, change):
    before = learn.get("/api/v1/learn/articles/tokenized-stocks").json()
    data = json.loads(Settings().learn_articles_path.read_text())
    data["articles"][0]["title"] = "Should never persist"
    if change == "duplicate":
        data["articles"].append(data["articles"][0])
    elif change == "invalid_slug":
        data["articles"][-1]["slug"] = "invalid slug"
    elif change == "missing_content":
        data["articles"][-1]["content"] = ""
    else:
        data["articles"] = []
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))

    async def check():
        async with learn.db_factory() as session:
            with pytest.raises(ValueError):
                await seed_articles(session, path)
            rows = list(await session.scalars(select(LearnArticle)))
            assert len(rows) == 8

    learn.portal.call(check)
    assert learn.get("/api/v1/learn/articles/tokenized-stocks").json() == before


def test_empty_list_is_success(client):
    assert client.get("/api/v1/learn/articles").json() == {"data": []}
