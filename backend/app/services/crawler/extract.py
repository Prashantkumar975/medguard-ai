"""HTML content extraction: Trafilatura primary, BeautifulSoup fallback."""
from __future__ import annotations

import hashlib
import re

from bs4 import BeautifulSoup
import trafilatura
from trafilatura.settings import use_config

_cfg = use_config()
_cfg.set("DEFAULT", "EXTRACTION_TIMEOUT", "10")

# Markers that commonly indicate a JS-rendered shell with no server HTML.
_SHELL_MARKERS = ('id="root"', 'id="app"', "window.__NEXT_DATA__", "This application requires JavaScript")


def extract_text(html: str) -> str:
    """Extract readable main content. Trafilatura first, then BS4 article/Body fallback."""
    text = trafilatura.extract(html, config=_cfg, include_comments=False, include_tables=True)
    if text and len(text.strip()) >= 80:
        return _normalize(text)

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()
    node = soup.find("article") or soup.find("main") or soup.body or soup
    fallback = node.get_text(separator="\n", strip=True) if node else ""
    return _normalize(fallback)


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def needs_js_render(html: str, text: str) -> bool:
    """Heuristic: shell page with almost no server-rendered text."""
    if len(text) > 400:
        return False
    lowered = html.lower()
    return any(marker.lower() in lowered for marker in _SHELL_MARKERS)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def render_js(url: str) -> str | None:
    """Optional Playwright fallback for JS-heavy pages. Returns None when the
    browser runtime is unavailable — callers must treat that as a fetch failure,
    never as empty content."""
    if not settings_js_render_enabled():
        return None
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None
    from app.core.config import settings

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, timeout=settings.js_render_timeout_s * 1000, wait_until="networkidle")
                return await page.content()
            finally:
                await browser.close()
    except Exception:
        return None


def settings_js_render_enabled() -> bool:
    from app.core.config import settings

    return settings.js_render_enabled
