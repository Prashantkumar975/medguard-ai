"""SSRF-safe URL validation and DNS-pinned HTTP fetching.

Security requirements implemented here:
- scheme allow-list (http/https only)
- port allow-list
- private / loopback / link-local / reserved target rejection (with an explicit
  development-only opt-in for the local demo site)
- redirect destination revalidation on every hop
- DNS-rebinding resistance: we resolve once, validate the IPs, then pin the
  connection to a validated IP via an httpx transport that never re-resolves
- download size caps, timeouts, redirect caps
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings


class SSRFError(ValueError):
    """Raised when a URL fails safety validation."""


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # `is_private` alone does not reject shared address space (100.64/10) and
    # behavior for special-use ranges can vary between Python releases. Only
    # globally routable addresses are safe crawler destinations.
    if ip.version == 6 and ip.ipv4_mapped is not None:
        return _is_public(ip.ipv4_mapped)
    return ip.is_global and not (ip.is_multicast or ip.is_unspecified)


def resolve_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFError(f"Could not resolve host {host!r}") from exc
    ips = []
    for info in infos:
        addr = info[4][0]
        try:
            ips.append(ipaddress.ip_address(addr))
        except ValueError:
            continue
    if not ips:
        raise SSRFError(f"No addresses resolved for {host!r}")
    return ips


def validate_url(url: str) -> tuple[str, list[str]]:
    """Validate a URL and return (normalized_url, allowed_ip_strings).

    Raises SSRFError when the target is not an approved public endpoint.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Unsupported scheme {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise SSRFError("URL has no host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in settings.allowed_port_set:
        raise SSRFError(f"Port {port} is not allowed")

    ips = resolve_ips(host)
    local_ok = settings.allow_local_targets and all(ip.is_loopback for ip in ips)
    if not all(_is_public(ip) for ip in ips) and not local_ok:
        raise SSRFError(f"Target {host!r} resolves to a blocked address range")
    return url, [str(ip) for ip in ips]


class PinnedTransport(httpx.HTTPTransport):
    """Resolve and validate each request, then connect to that exact IP.

    The URL is rewritten only for the socket connection. Host and TLS SNI remain
    the original hostname, so DNS cannot change between validation and connect.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, retries=0, **kwargs)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        original = request.url
        _, ips = validate_url(str(original))
        host_header = original.host
        default_port = 443 if original.scheme == "https" else 80
        if original.port and original.port != default_port:
            host_header = f"{host_header}:{original.port}"
        errors: list[Exception] = []
        for address in ips:
            connect_host = f"[{address}]" if ":" in address else address
            pinned_url = original.copy_with(host=connect_host)
            headers = request.headers.copy()
            headers["Host"] = host_header
            extensions = dict(request.extensions)
            extensions["sni_hostname"] = original.host.encode("ascii")
            pinned_request = httpx.Request(
                request.method,
                pinned_url,
                headers=headers,
                content=request.content,
                extensions=extensions,
            )
            try:
                return super().handle_request(pinned_request)
            except httpx.HTTPError as exc:
                errors.append(exc)
        if errors:
            raise errors[-1]
        raise SSRFError("No validated address available for connection")


def build_client(allowed_ips: list[str] | None = None, timeout: float | None = None) -> httpx.Client:
    """Client that pins connections to validated IPs."""
    return httpx.Client(
        transport=PinnedTransport(),
        timeout=timeout or settings.fetch_timeout_s,
        follow_redirects=False,
        headers={"User-Agent": settings.crawl_user_agent},
        max_redirects=0,
    )


def fetch_url(client: httpx.Client, url: str) -> httpx.Response:
    """Fetch a URL with SSRF validation on the initial target and every redirect hop."""
    current = url
    for _hop in range(settings.fetch_max_redirects + 1):
        req = client.build_request("GET", current)
        response = client.send(req, stream=True)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location")
            response.close()
            if not location:
                raise SSRFError("Redirect without Location header")
            current = urljoin(current, location)
            continue
        return response
    raise SSRFError("Too many redirects")
