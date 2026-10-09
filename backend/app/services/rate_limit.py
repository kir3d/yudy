import hashlib

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.core.config import Settings

SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""


class AuthRateLimiter:
    def __init__(self, redis, settings: Settings):
        self.redis = redis
        self.settings = settings

    async def check(self, identity):
        if self.redis is None:
            raise HTTPException(503, "Authentication is temporarily unavailable")
        key = "auth-rate:" + hashlib.sha256(identity.encode()).hexdigest()
        try:
            count = await self.redis.eval(SCRIPT, 1, key, self.settings.auth_rate_window_seconds)
        except RedisError:
            raise HTTPException(503, "Authentication is temporarily unavailable") from None
        if count > self.settings.auth_rate_limit:
            raise HTTPException(
                429,
                "Too many authentication attempts. Try again later.",
                headers={"Retry-After": str(self.settings.auth_rate_window_seconds)},
            )
