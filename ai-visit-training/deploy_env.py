"""Shared environment-only configuration for legacy deployment utilities."""

import os


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


DEPLOY_HOST = _required("DEPLOY_HOST")
DEPLOY_PORT = int(os.getenv("DEPLOY_PORT", "22"))
DEPLOY_USER = os.getenv("DEPLOY_USER", "root").strip() or "root"
DEPLOY_PASSWORD = _required("DEPLOY_PASSWORD")
