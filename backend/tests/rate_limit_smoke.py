"""Run inside the backend container to verify the Redis rate limiter."""

import asyncio
import hashlib
import uuid

from fastapi import HTTPException
from redis.asyncio import Redis

from app.core.config import get_settings
from app.services.rate_limit import AuthRateLimiter


async def main():
    settings = get_settings().model_copy(
        update={"auth_rate_limit": 2, "auth_rate_window_seconds": 1}
    )
    redis = Redis.from_url(settings.redis_url)
    identity = "smoke-" + uuid.uuid4().hex
    key = "auth-rate:" + hashlib.sha256(identity.encode()).hexdigest()
    try:
        limiter = AuthRateLimiter(redis, settings)
        await limiter.check(identity)
        await limiter.check(identity)
        try:
            await limiter.check(identity)
        except HTTPException as error:
            assert error.status_code == 429
            assert error.headers["Retry-After"] == "1"
        else:
            raise AssertionError("Expected rate limit")
        await asyncio.sleep(1.1)
        await limiter.check(identity)
        print("PASS: Redis blocks excess auth attempts and resets after expiry")
    finally:
        await redis.delete(key)
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
