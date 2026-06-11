# Copyright 2026 Kroonen AI (https://kroonen.ai)
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import secrets


@dataclass(frozen=True)
class SearxngFiles:
    root: Path
    compose_path: Path
    settings_path: Path
    env_path: Path


def default_searxng_path() -> Path:
    return Path.home() / ".libre-claw" / "searxng"


def ensure_searxng_files(root: Path | None = None) -> SearxngFiles:
    target = (root or default_searxng_path()).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    files = SearxngFiles(
        root=target,
        compose_path=target / "docker-compose.yml",
        settings_path=target / "settings.yml",
        env_path=target / ".env",
    )
    if not files.compose_path.exists():
        files.compose_path.write_text(_compose_text(), encoding="utf-8")
    if not files.settings_path.exists():
        files.settings_path.write_text(_settings_text(secret_key=secrets.token_urlsafe(32)), encoding="utf-8")
    if not files.env_path.exists():
        files.env_path.write_text(_env_text(), encoding="utf-8")
    return files


def searxng_compose_command(root: Path, *args: str) -> list[str]:
    compose_file = root.expanduser() / "docker-compose.yml"
    return ["docker", "compose", "-f", str(compose_file), *args]


def _compose_text() -> str:
    return """services:
  searxng:
    image: searxng/searxng:latest
    container_name: libre-claw-searxng
    restart: unless-stopped
    ports:
      - "127.0.0.1:8888:8080"
    volumes:
      - ./settings.yml:/etc/searxng/settings.yml:ro
    environment:
      - SEARXNG_BASE_URL=http://127.0.0.1:8888/
      - UWSGI_WORKERS=4
      - UWSGI_THREADS=4
"""


def _settings_text(*, secret_key: str) -> str:
    return f"""use_default_settings: true

server:
  bind_address: "0.0.0.0"
  port: 8080
  secret_key: "{secret_key}"
  limiter: false
  image_proxy: false

search:
  safe_search: 0
  autocomplete: ""
  formats:
    - html
    - json

ui:
  static_use_hash: true
"""


def _env_text() -> str:
    return """# Libre Claw local SearXNG instance.
# The compose file binds to 127.0.0.1:8888 by default.
"""
