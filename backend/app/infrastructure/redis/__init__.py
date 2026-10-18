"""Redis infrastructure used by web-system modules."""

from app.infrastructure.redis.connection import get_activity_client, get_redis_client

__all__ = ["get_activity_client", "get_redis_client"]
