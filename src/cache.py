import json
import logging

import fakeredis

logger = logging.getLogger(__name__)


class MovieCache:
    def __init__(self):
        self.client = fakeredis.FakeRedis(decode_responses=True)

    def make_key(self, limit):
        return f"movies:limit:{limit}"

    def get(self, limit):
        """Return the cached response dictionary, or None."""
        key = self.make_key(limit)
        cached = self.client.get(key)

        if cached is None:
            logger.debug(f"Cache MISS: {key}")
            return None

        logger.debug(f"Cache HIT: {key}")
        # the cache stores text, so turn the JSON string back into a dict
        return json.loads(cached)

    def set(self, limit, response):
        """Cache the response dictionary for 90 seconds."""
        key = self.make_key(limit)
        # turn the dict into a JSON string; ex=90 means it expires after 90 seconds
        self.client.set(key, json.dumps(response), ex=90)

    def invalidate(self):
        """Remove all cached movie retrievals."""
        # this cache only holds movie responses, so clearing all of it is safe
        self.client.flushdb()
        logger.debug("Invalidated movie cache")
