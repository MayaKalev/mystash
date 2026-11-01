from redis import Redis
from rq import Queue

from app.config import REDIS_URL

# Jobs added here are picked up by the worker (`rq worker`).
queue = Queue(connection=Redis.from_url(REDIS_URL))
