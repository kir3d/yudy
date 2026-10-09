import hashlib
import json

from redis.exceptions import RedisError

from app.schemas.assets import CatalogMeta
from app.schemas.selection import SelectionEnvelope, SelectionItem


class SelectionService:
    def __init__(self, repository, assets, engine, redis, ttl, rules):
        self.repository = repository
        self.assets = assets
        self.engine = engine
        self.redis = redis
        self.ttl = ttl
        self.rules = rules

    async def feed(self, user_id, limit, cursor):
        signals, candidates, assets = await self.repository.snapshot(user_id)
        fingerprint = hashlib.sha256(
            json.dumps(
                [str(user_id), signals, candidates, self.rules],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        offset = self.assets.offset(cursor, fingerprint)
        key = f"yudy:selection:{user_id}:{fingerprint}"
        ranked = None
        if self.redis is not None:
            try:
                cached = await self.redis.get(key)
                if cached:
                    ranked = json.loads(cached)
            except (RedisError, ValueError, TypeError):
                pass
        if ranked is None:
            ranked = [
                {"id": r.asset_id, "reasons": r.reasons}
                for r in self.engine.rank_assets(signals, candidates)
            ]
            if self.redis is not None:
                try:
                    await self.redis.set(key, json.dumps(ranked), ex=self.ttl)
                except RedisError:
                    pass
        page = ranked[offset : offset + limit]
        by_id = {str(a.id): a for a in assets}
        summaries = await self.assets.summary([by_id[r["id"]] for r in page])
        return SelectionEnvelope(
            data=[
                SelectionItem(
                    asset=a,
                    interaction=signals["states"].get(
                        str(a.id), dict(liked=False, disliked=False, saved=False)
                    ),
                    reasons=r["reasons"],
                )
                for a, r in zip(summaries, page)
            ],
            meta=CatalogMeta(
                total=len(ranked),
                next_cursor=self.assets.cursor(offset + len(page), fingerprint)
                if offset + len(page) < len(ranked)
                else None,
            ),
        )
