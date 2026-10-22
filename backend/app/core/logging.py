"""Structured logging setup."""
import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)
    # Quiet noisy libs
    for noisy in ("httpx", "httpcore", "trafilatura", "charset_normalizer", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
