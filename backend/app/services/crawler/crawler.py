"""The controlled crawler: discovery, fetching, change detection, snapshots."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Page, Scan, Site, Snapshot
from app.services.crawler import robots
from app.services.crawler.extract import content_hash, extract_text, needs_js_render, render_js  # noqa: F401
from app.services.crawler.security import SSRFError, build_client, fetch_url, validate_url

log = logging.getLogger(__name__)


@dataclass
class PageResult:
    url: str
    http_status: int
    text: str
    content_hash: str
    changed: bool
    snapshot_id: str | None = None
    extraction_pending: bool = False
    last_modified: datetime | None = None
    error: str | None = None


@dataclass
class CrawlResult:
    pages: list[PageResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _same_site(url: str, netloc: str) -> bool:
    return urlparse(url).netloc == netloc


def site_base_url(domain: str) -> str:
    """Seed URL for a registered domain. Loopback targets use http in dev/demo mode."""
    host = domain.split(":")[0]
    if settings.allow_local_targets and host in ("localhost", "127.0.0.1", "0.0.0.0"):
        return f"http://{domain}/"
    return f"https://{domain}/"


def parse_last_modified(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def discover_urls(client: httpx.Client, site: Site, max_pages: int) -> list[str]:
    """Discover approved pages via robots, sitemaps and bounded link following."""
    seed = site_base_url(site.domain)
    allowed_netloc = urlparse(seed).netloc
    urls: list[str] = []
    seen: set[str] = set()

    # 1. sitemaps from robots.txt
    parser = robots.get_robots(client, seed)
    sitemap_urls = list(getattr(parser, "site_entries", []) or [])
    if not sitemap_urls:
        sitemap_urls = [urljoin(seed, "sitemap.xml")]
    for sm in sitemap_urls[:3]:
        try:
            validate_url(sm)
            resp = client.get(sm, timeout=10.0)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "xml")
            for loc in soup.find_all("loc"):
                u = (loc.text or "").strip()
                if u and _same_site(u, allowed_netloc) and u not in seen:
                    seen.add(u)
                    urls.append(u)
                    if len(urls) >= max_pages:
                        break
        except (SSRFError, httpx.HTTPError) as exc:
            log.info("sitemap %s skipped: %s", sm, exc)
        if len(urls) >= max_pages:
            break

    # 2. bounded BFS over internal links when sitemaps gave little
    frontier = [seed]
    visited: set[str] = set()
    while frontier and len(urls) < max_pages:
        current = frontier.pop(0)
        if current in visited:
            continue
        visited.add(current)
        if not robots.can_fetch(client, current):
            continue
        try:
            robots.polite_wait(client, current)
            response = fetch_url(client, current)
            html = response.read().decode("utf-8", errors="replace")
            response.close()
        except (SSRFError, httpx.HTTPError) as exc:
            log.info("discover fetch failed %s: %s", current, exc)
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            u = urljoin(current, a["href"].split("#")[0])
            p = urlparse(u)
            if p.scheme not in ("http", "https") or not _same_site(u, allowed_netloc):
                continue
            if u in seen:
                continue
            seen.add(u)
            if robots.can_fetch(client, u):
                urls.append(u)
            if len(urls) >= max_pages:
                break
            if u not in visited:
                frontier.append(u)
    return urls[:max_pages]


def crawl_site(db: Session, scan: Scan, site: Site, *, max_pages: int | None = None,
               only_urls: list[str] | None = None) -> CrawlResult:
    """Crawl a site under budget, storing versioned snapshots with change detection."""
    budget = max_pages or scan.max_pages or settings.crawl_max_pages_per_scan
    result = CrawlResult()
    with build_client(timeout=settings.fetch_timeout_s) as client:
        try:
            urls = only_urls or discover_urls(client, site, budget)
        except Exception as exc:
            result.errors.append(f"Discovery failed: {exc}")
            scan.error = "; ".join(result.errors)
            db.commit()
            return result

        scan.pages_total = len(urls)
        db.commit()

        for url in urls:
            if scan.status == "cancelled":
                break
            try:
                robots.polite_wait(client, url)
                if not robots.can_fetch(client, url):
                    result.errors.append(f"robots.txt disallowed: {url}")
                    continue
                validate_url(url)
                response = fetch_url(client, url)
                status = response.status_code
                # cap download size while streaming (httpx read() takes no size arg)
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= settings.fetch_max_bytes:
                        break
                raw = b"".join(chunks)[: settings.fetch_max_bytes]
                last_mod_header = response.headers.get("last-modified")
                response.close()
                if status >= 400:
                    result.errors.append(f"HTTP {status} for {url}")
                    scan.pages_done += 1
                    db.commit()
                    continue
                html = raw.decode("utf-8", errors="replace")
            except (SSRFError, httpx.HTTPError, UnicodeDecodeError) as exc:
                result.errors.append(f"{url}: {exc}")
                scan.pages_done += 1
                db.commit()
                continue

            text = extract_text(html)
            if needs_js_render(html, text) and settings.js_render_enabled:
                import asyncio

                rendered = asyncio.run(render_js(url))
                if rendered:
                    html = rendered
                    text = extract_text(html)

            page = db.scalar(
                select(Page).where(Page.site_id == site.id, Page.url == url).with_for_update()
            )
            if page is None:
                from sqlalchemy.exc import IntegrityError

                try:
                    with db.begin_nested():
                        page = Page(site_id=site.id, url=url)
                        db.add(page)
                        db.flush()
                except IntegrityError:
                    page = db.scalar(
                        select(Page).where(Page.site_id == site.id, Page.url == url).with_for_update()
                    )
                if page is None:
                    raise RuntimeError(f"Page row could not be created or loaded for {url}")

            h = content_hash(text)
            previous = db.scalar(
                select(Snapshot).where(Snapshot.page_id == page.id).order_by(Snapshot.version.desc()).limit(1)
            )
            changed = previous is None or previous.content_hash != h
            snapshot = Snapshot(
                page_id=page.id,
                site_id=site.id,
                scan_id=scan.id,
                url=url,
                http_status=status,
                content_hash=h,
                # Avoid storing the same full page text on every unchanged scan.
                text_content=text if changed else "",
                version=(previous.version + 1) if previous else 1,
                changed=changed,
                last_modified=parse_last_modified(last_mod_header),
                extraction_status=("pending" if changed or previous.extraction_status != "completed" else "completed"),
            )
            db.add(snapshot)
            db.flush()
            page.last_snapshot_id = snapshot.id
            page.last_seen_at = datetime.now(timezone.utc)
            result.pages.append(
                PageResult(url=url, http_status=status, text=text, content_hash=h, changed=changed,
                           snapshot_id=snapshot.id,
                           extraction_pending=snapshot.extraction_status != "completed",
                           last_modified=snapshot.last_modified)
            )
            scan.pages_done += 1
            if changed:
                scan.changed += 1
            db.commit()

    site.pages = max(site.pages, len(urls))
    site.last_scan_at = datetime.now(timezone.utc)
    db.commit()
    return result
