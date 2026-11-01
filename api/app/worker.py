"""Background worker (arq). Week 1: a stub so the container runs; Week 2 adds the real pipeline."""

import logging
from typing import Any

from arq.connections import RedisSettings

from app.config import get_settings

logger = logging.getLogger(__name__)


async def process_item(ctx: dict[str, Any], item_id: str) -> None:
    logger.info("process_item called for %s (pipeline not implemented yet)", item_id)


class WorkerSettings:
    functions = [process_item]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
