import asyncio
import time
from collections import defaultdict
from urllib.parse import urlparse

from asyncio import Semaphore

_domain_semaphores: dict[str, Semaphore] = defaultdict(lambda: Semaphore(1))
_domain_last_call: dict[str, float] = {}
MIN_DELAY_SECONDS = 1.0


async def throttled_get(client, url, **kwargs):
    domain = urlparse(url).netloc
    async with _domain_semaphores[domain]:
        now = time.monotonic()
        last = _domain_last_call.get(domain, 0)
        wait = max(0, MIN_DELAY_SECONDS - (now - last))
        if wait:
            await asyncio.sleep(wait)
        _domain_last_call[domain] = time.monotonic()
        return await client.get(url, **kwargs)
