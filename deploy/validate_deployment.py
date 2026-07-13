"""Static validation for the deployment templates when Docker is unavailable."""

from pathlib import Path
import re
import sys

import yaml


ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"


def main() -> int:
    compose = yaml.safe_load((DEPLOY / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose.get("services", {})
    required = {
        "unified-portal", "customer-intelligence-api", "customer-intelligence-frontend", "ai-training", "nginx"
    }
    assert required <= set(services), f"missing services: {required - set(services)}"
    assert services["nginx"].get("ports") == ["${GATEWAY_PORT:-8080}:8080"]
    for name in required:
        assert "healthcheck" in services[name], f"{name} has no healthcheck"
    assert services["ai-training"]["environment"]["ASR_ENABLED"] == "false"
    assert services["customer-intelligence-api"]["environment"]["TRAINING_SERVICE_BASE_URL"] == "http://ai-training:5000"

    nginx = (DEPLOY / "nginx.conf").read_text(encoding="utf-8")
    for route in ("/intelligence-api/", "/intelligence/", "/api/", "/training/", "/"):
        assert f"location {route}" in nginx

    files = [
        ROOT / "unified-portal/Dockerfile",
        ROOT / "customer-intelligence/Dockerfile.api",
        ROOT / "customer-intelligence/frontend/Dockerfile",
        ROOT / "ai-visit-training/Dockerfile",
    ]
    for path in files:
        assert path.is_file(), f"missing {path}"

    scanned = "\n".join(path.read_text(encoding="utf-8") for path in [DEPLOY / "docker-compose.yml", DEPLOY / ".env.example"])
    assert not re.search(r"sk-[A-Za-z0-9_-]{20,}", scanned)
    assert "replace-with-secret" in scanned
    print("Deployment templates passed static validation")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, TypeError) as exc:
        print(f"Deployment validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
