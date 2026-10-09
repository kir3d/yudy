import copy

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from test_risk import account, answers, questionnaire

from app.core.config import Settings
from app.main import app
from app.personalization.engine import RuleBasedEngine
from app.personalization.weights import RankingWeights
from app.services.asset_seed import seed_assets


def signals():
    return dict(
        experience="EXPERIENCED",
        horizon="UNDER_ONE",
        risk="Growth",
        interests=[],
        excluded=[],
        regions=[],
        goals=[],
        states={},
        viewed=[],
    )


def candidates():
    return [
        dict(
            id=str(i),
            symbol=f"D{i}",
            sector=sector,
            industry=sector,
            region="usa",
            country="USA",
            asset_type="STOCK",
            themes=[theme],
            has_dividend=False,
        )
        for i, sector, theme in [
            (1, "Automotive", "green_energy"),
            (2, "Automotive", "green_energy"),
            (3, "Healthcare", "health"),
        ]
    ]


def score_map(s):
    return {r.asset_id: r for r in RuleBasedEngine(RankingWeights()).rank_assets(s, candidates())}


@pytest.mark.parametrize(
    "kind,code,title",
    [("SECTOR", "automotive", "Automotive"), ("THEME", "green_energy", "Green Energy")],
)
def test_interest_and_exclusion_change_rank_and_truthful_reasons(kind, code, title):
    s = signals()
    interest = dict(kind=kind, code=code, title=title)
    s["interests"] = [interest]
    positive = score_map(s)
    assert positive["1"].score > positive["3"].score
    assert title in positive["1"].reasons[0]["text"]
    assert not any(r["type"] == "interest_match" for r in positive["3"].reasons)
    s["interests"] = []
    s["excluded"] = [interest]
    negative = score_map(s)
    assert negative["1"].score < negative["3"].score
    assert negative["1"].reasons[0]["type"] == "excluded_interest"


def test_dislike_lowers_similar_assets_and_save_is_not_like():
    s = signals()
    s["states"]["1"] = dict(liked=False, disliked=True, saved=False)
    ranked = score_map(s)
    assert ranked["1"].score < ranked["2"].score < ranked["3"].score
    s["states"]["1"] = dict(liked=False, disliked=False, saved=True)
    saved = score_map(s)
    assert saved["1"].score > 0 and saved["2"].score > 0
    assert all(not r["type"].startswith("like") for r in saved["1"].reasons)
    s["states"]["1"] = dict(liked=True, disliked=False, saved=False)
    liked = score_map(s)
    assert liked["1"].score != saved["1"].score
    assert liked["2"].score != saved["2"].score


def test_views_are_weak_bounded_and_ranking_is_deterministic():
    s = signals()
    s["viewed"] = ["1", "2"]
    engine = RuleBasedEngine(RankingWeights())
    first = engine.rank_assets(s, candidates())
    assert first == engine.rank_assets(copy.deepcopy(s), list(reversed(candidates())))
    assert all(0 <= item.score <= 1 for item in first)
    assert all(1 <= len(item.reasons) <= 3 for item in first)
    assert score_map(signals())["1"].reasons[0]["type"] == "catalog"


def test_configurable_weights_and_zero_weight_never_invent_reasons():
    s = signals()
    s["regions"] = [dict(code="usa", title="USA")]
    engine = RuleBasedEngine(RankingWeights(region_match=0))
    assert all(
        r.score == 0 and r.reasons[0]["type"] == "catalog"
        for r in engine.rank_assets(s, candidates())
    )
    with pytest.raises(ValueError):
        RankingWeights(region_match=float("nan"))


class MemoryRedis:
    def __init__(self):
        self.data = {}
        self.writes = 0
        self.fail = False

    async def get(self, key):
        if self.fail:
            raise RedisConnectionError("test unavailable")
        return self.data.get(key)

    async def set(self, key, value, ex):
        if self.fail:
            raise RedisConnectionError("test unavailable")
        assert ex > 0
        self.writes += 1
        self.data[key] = value


@pytest.fixture
def selection(client):
    async def seed():
        async with client.db_factory() as session:
            await seed_assets(session, Settings().demo_market_path)

    client.portal.call(seed)
    headers = account(client)
    assert (
        client.post(
            "/api/v1/risk/assessment",
            headers=headers,
            json=answers(questionnaire(client, headers), 3),
        ).status_code
        == 200
    )
    cache = MemoryRedis()
    app.state.redis = cache
    yield client, headers, cache
    app.state.redis = None


def feed(selection, **params):
    client, headers, _ = selection
    response = client.get("/api/v1/selection/for-you", headers=headers, params=params)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "score" not in response.text
    return response.json()


def test_full_paging_cache_and_user_bound_cursor(selection):
    client, headers, cache = selection
    first = feed(selection, limit=7)
    assert cache.writes == 1
    assert feed(selection, limit=7) == first and cache.writes == 1
    items = list(first["data"])
    cursor = first["meta"]["next_cursor"]
    while cursor:
        page = feed(selection, cursor=cursor, limit=7)
        items.extend(page["data"])
        cursor = page["meta"]["next_cursor"]
    assert len({i["asset"]["id"] for i in items}) == len(items) == 36
    assert all(1 <= len(i["reasons"]) <= 3 for i in items)
    assert cache.writes == 1
    other = account(client, email="other-selection@example.com")
    client.post(
        "/api/v1/risk/assessment", headers=other, json=answers(questionnaire(client, other), 3)
    )
    assert (
        client.get(
            "/api/v1/selection/for-you",
            headers=other,
            params={"cursor": first["meta"]["next_cursor"]},
        ).status_code
        == 400
    )


@pytest.mark.parametrize("action", ["like", "dislike", "save", "view"])
def test_action_invalidates_cache_cursor_and_discover_unaffected(selection, action):
    client, headers, cache = selection
    public = client.get("/api/v1/assets?limit=50").json()
    before = feed(selection, limit=5)
    original = feed(selection, limit=50)
    asset_id = before["data"][-1]["asset"]["id"]
    assert client.post(f"/api/v1/assets/{asset_id}/{action}", headers=headers).status_code == 200
    after = feed(selection, limit=50)
    assert cache.writes == 2
    assert after["data"] != original["data"]
    if action in ("like", "dislike", "save"):

        def position(items):
            return next(i for i, item in enumerate(items) if item["asset"]["id"] == asset_id)

        assert (
            (position(after["data"]) > position(original["data"]))
            if action == "dislike"
            else (position(after["data"]) < position(original["data"]))
        )
    assert (
        client.get(
            "/api/v1/selection/for-you",
            headers=headers,
            params={"cursor": before["meta"]["next_cursor"]},
        ).status_code
        == 400
    )
    assert client.get("/api/v1/assets?limit=50").json() == public
    if action != "view":
        client.delete(f"/api/v1/assets/{asset_id}/{action}", headers=headers)
        reset = feed(selection, limit=5)
        assert reset["data"] == before["data"]


def test_profile_risk_changes_and_redis_outage(selection):
    client, headers, cache = selection
    first = feed(selection, limit=5)
    profile = client.get("/api/v1/profile", headers=headers).json()["data"]
    interest = next(
        i for i in client.get("/api/v1/interests").json()["data"] if i["code"] == "automotive"
    )
    body = {
        k: profile[k]
        for k in [
            "experience",
            "investment_horizon",
            "goal_ids",
            "interest_ids",
            "excluded_interest_ids",
            "region_ids",
        ]
    }
    body["interest_ids"] = [interest["id"]]
    assert client.put("/api/v1/profile", headers=headers, json=body).status_code == 200
    updated = feed(selection, limit=5)
    assert updated != first and cache.writes == 2
    assert any(r["type"] == "interest_match" for item in updated["data"] for r in item["reasons"])
    client.post(
        "/api/v1/risk/assessment", headers=headers, json=answers(questionnaire(client, headers), 0)
    )
    feed(selection, limit=5)
    assert cache.writes == 3
    cache.fail = True
    assert feed(selection, limit=5)["data"]


def test_selection_prerequisites(client):
    assert client.get("/api/v1/selection/for-you").status_code == 401
    headers = account(client)
    assert client.get("/api/v1/selection/for-you", headers=headers).status_code == 409
