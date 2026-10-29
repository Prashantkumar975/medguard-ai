"""robots.txt handling with caching and crawl-delay support."""
from __future__ import annotations

import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import settings
from app.services.crawler.security import SSRFError, validate_url

log = logging.getLogger(__name__)

_cache: dict[str, tuple[RobotFileParser, float]] = {}
_last_fetch: dict[str, float] = {}


def _robots_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}/robots.txt"


def get_robots(client: httpx.Client, url: str) -> RobotFileParser:
    """Fetch and cache robots.txt for a site. A missing robots.txt allows all."""
    p = urlparse(url)
    key = p.netloc
    cached = _cache.get(key)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    parser = RobotFileParser()
    parser.set_url(_robots_url(url))
    try:
        validate_url(parser.url)
        resp = client.get(parser.url, timeout=10.0)
        if resp.status_code == 200:
            parser.parse(resp.text.splitlines())
        else:
            parser.allow_all = True
    except (SSRFError, httpx.HTTPError) as exc:
        log.warning("robots.txt fetch failed for %s: %s", key, exc)
        parser.allow_all = True
    _cache[key] = (parser, time.monotonic() + max(60, settings.robots_cache_ttl_s))
    return parser


def can_fetch(client: httpx.Client, url: str) -> bool:
    parser = get_robots(client, url)
    if parser.allow_all:
        return True
    if parser.disallow_all:
        return False
    return parser.can_fetch(settings.crawl_user_agent, url)


def crawl_delay(client: httpx.Client, url: str) -> float:
    parser = get_robots(client, url)
    delay = parser.crawl_delay(settings.crawl_user_agent) or 0
    return max(float(delay) * 1.0, settings.crawl_delay_ms / 1000.0)


def polite_wait(client: httpx.Client, url: str) -> None:
    delay = crawl_delay(client, url)
    last = _last_fetch.get(urlparse(url).netloc, 0.0)
    wait = last + delay - time.monotonic()
    if wait > 0:
        time.sleep(min(wait, 5.0))
    _last_fetch[urlparse(url).netloc] = time.monotonic()
