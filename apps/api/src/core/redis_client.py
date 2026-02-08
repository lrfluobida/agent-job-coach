from __future__ import annotations

from redis import Redis

from src.core.settings import get_settings


_CLIENT: Redis | None = None


def get_redis_client() -> Redis:
    global _CLIENT
    if _CLIENT is None:
        cfg = get_settings()
        _CLIENT = Redis(
            host=cfg.redis_host,
            port=cfg.redis_port,
            db=cfg.redis_db,
            password=cfg.redis_password,
            username=cfg.redis_username,
            ssl=cfg.redis_ssl,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=3.0,
            health_check_interval=30,
        )
    return _CLIENT

