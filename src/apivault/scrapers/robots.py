from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

_robots_cache: dict[str, RobotFileParser] = {}


async def is_allowed(url: str, user_agent: str = "APIVault") -> bool:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    if base not in _robots_cache:
        rp = RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            rp.read()
        except Exception:
            return True
        _robots_cache[base] = rp

    return _robots_cache[base].can_fetch(user_agent, url)
