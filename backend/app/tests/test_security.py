"""SSRF protection and URL-validation tests (brief section 20)."""
import pytest

from app.services.crawler.security import SSRFError, validate_url


def test_rejects_non_http_schemes():
    for url in ("ftp://example.com/x", "file:///etc/passwd", "gopher://x", "javascript:alert(1)"):
        with pytest.raises(SSRFError):
            validate_url(url)


def test_rejects_disallowed_ports():
    with pytest.raises(SSRFError):
        validate_url("https://example.com:22/")
    with pytest.raises(SSRFError):
        validate_url("http://example.com:6379/")


def test_rejects_loopback_and_private_by_default(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "allow_local_targets", False)
    for url in ("http://127.0.0.1/", "http://localhost/", "http://10.0.0.5/", "http://192.168.1.1/", "http://169.254.169.254/latest/meta-data/"):
        with pytest.raises(SSRFError):
            validate_url(url)


def test_rejects_metadata_endpoint(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "allow_local_targets", False)
    with pytest.raises(SSRFError):
        validate_url("http://169.254.169.254/latest/meta-data/iam/security-credentials/")


def test_allows_local_when_explicitly_enabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "allow_local_targets", True)
    _, ips = validate_url("http://127.0.0.1:8090/")
    assert ips  # resolves and is permitted in dev mode


def test_public_host_resolves(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "allow_local_targets", False)

    # Inject a fake resolver so this test does not depend on live DNS.
    import app.services.crawler.security as sec
    import ipaddress

    monkeypatch.setattr(sec, "resolve_ips", lambda host: [ipaddress.ip_address("93.184.216.34")])
    _, ips = validate_url("https://example.com/page")
    assert ips == ["93.184.216.34"]
