"""Entry point for Libre Claw."""

import argparse
import json
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import uvicorn

from .agent import Agent
from .api import create_app
from .backends import BackendConfig, get_backend
from .config import Config
from .memory import MemoryManager
from .tui import start_tui
from .workspace import Workspace


GATEWAY_SERVICE_LABEL = "ai.kroonen.libre_claw.gateway"
GATEWAY_SYSTEMD_SERVICE = "libre-claw-gateway.service"
DEFAULT_CURATED_SKILLS = [
    {
        "name": "coding-agent",
        "source": "https://github.com/openclaw/openclaw.git#skills/coding-agent",
        "description": "OpenClaw coding-focused skill.",
    },
    {
        "name": "healthcheck",
        "source": "https://github.com/openclaw/openclaw.git#skills/healthcheck",
        "description": "OpenClaw service health checks and runbook patterns.",
    },
    {
        "name": "github",
        "source": "https://github.com/openclaw/openclaw.git#skills/github",
        "description": "OpenClaw GitHub operations skill.",
    },
    {
        "name": "skill-creator",
        "source": str(Path.home() / ".codex" / "skills" / ".system" / "skill-creator"),
        "description": "Codex skill authoring guide.",
    },
    {
        "name": "skill-installer",
        "source": str(Path.home() / ".codex" / "skills" / ".system" / "skill-installer"),
        "description": "Codex skill installation workflows.",
    },
]


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _is_linux() -> bool:
    return sys.platform.startswith("linux")


def _gateway_service_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{GATEWAY_SERVICE_LABEL}.plist"


def _gateway_service_systemd_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / GATEWAY_SYSTEMD_SERVICE


def _gateway_env_overrides() -> dict[str, str]:
    keys = [
        "LIBRE_CLAW_TOOL_MODE",
        "LIBRE_CLAW_CONTAINER_PERSISTENT",
        "LIBRE_CLAW_CONTAINER_ENGINE",
        "LIBRE_CLAW_CONTAINER_IMAGE",
        "LIBRE_CLAW_CONTAINER_SHELL",
        "LIBRE_CLAW_CONTAINER_MEMORY",
        "LIBRE_CLAW_CONTAINER_CPUS",
        "LIBRE_CLAW_CONTAINER_UID",
        "LIBRE_CLAW_CONTAINER_GID",
    ]
    env: dict[str, str] = {}
    for key in keys:
        value = os.getenv(key)
        if value:
            env[key] = value
    return env


def _install_gateway_service(workspace: str, host: str, port: int) -> int:
    logs_dir = Path.home() / ".libre-claw" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    env_vars = _gateway_env_overrides()

    if _is_macos():
        plist_path = _gateway_service_plist_path()
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "Label": GATEWAY_SERVICE_LABEL,
            "ProgramArguments": [
                sys.executable,
                "-m",
                "libre_claw",
                "--gateway",
                "--workspace",
                workspace,
                "--gateway-host",
                host,
                "--gateway-port",
                str(port),
            ],
            "RunAtLoad": True,
            "KeepAlive": True,
            "WorkingDirectory": str(Path.home()),
            "StandardOutPath": str(logs_dir / "gateway.out.log"),
            "StandardErrorPath": str(logs_dir / "gateway.err.log"),
        }
        if env_vars:
            payload["EnvironmentVariables"] = env_vars

        with plist_path.open("wb") as f:
            plistlib.dump(payload, f)
        print(f"Installed launchd service file: {plist_path}")
        print("Next step: libre-claw --gateway-service start")
        return 0

    if _is_linux():
        unit_path = _gateway_service_systemd_path()
        unit_path.parent.mkdir(parents=True, exist_ok=True)
        exec_parts = [
            sys.executable,
            "-m",
            "libre_claw",
            "--gateway",
            "--workspace",
            workspace,
            "--gateway-host",
            host,
            "--gateway-port",
            str(port),
        ]
        env_lines = "".join(
            f"Environment={key}={shlex.quote(value)}\n"
            for key, value in env_vars.items()
        )
        unit = (
            "[Unit]\n"
            "Description=Libre Claw Gateway\n"
            "After=network.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"ExecStart={shlex.join(exec_parts)}\n"
            "Restart=always\n"
            "RestartSec=3\n"
            "WorkingDirectory=%h\n"
            f"StandardOutput=append:{logs_dir / 'gateway.out.log'}\n"
            f"StandardError=append:{logs_dir / 'gateway.err.log'}\n"
            f"{env_lines}"
            "\n[Install]\n"
            "WantedBy=default.target\n"
        )
        unit_path.write_text(unit)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        print(f"Installed systemd user service file: {unit_path}")
        print("Next step: libre-claw --gateway-service start")
        return 0

    print(f"Gateway service install not supported on platform: {sys.platform}")
    return 1


def _start_gateway_service() -> int:
    if _is_macos():
        plist_path = _gateway_service_plist_path()
        if not plist_path.exists():
            print(f"Service file missing: {plist_path}")
            print("Run: libre-claw --gateway-service install -w <workspace>")
            return 1

        domain = f"gui/{os.getuid()}"
        bootstrap = subprocess.run(
            ["launchctl", "bootstrap", domain, str(plist_path)],
            capture_output=True,
            text=True,
        )
        if bootstrap.returncode != 0:
            err = (bootstrap.stderr or bootstrap.stdout or "").lower()
            if "already bootstrapped" not in err:
                print((bootstrap.stderr or bootstrap.stdout or "").strip())
                return 1

        kickstart = subprocess.run(
            ["launchctl", "kickstart", "-k", f"{domain}/{GATEWAY_SERVICE_LABEL}"],
            capture_output=True,
            text=True,
        )
        if kickstart.returncode != 0:
            print((kickstart.stderr or kickstart.stdout or "").strip())
            return 1

        print("Gateway service started (launchd).")
        return 0

    if _is_linux():
        started = subprocess.run(
            ["systemctl", "--user", "enable", "--now", GATEWAY_SYSTEMD_SERVICE],
            capture_output=True,
            text=True,
        )
        if started.returncode != 0:
            print((started.stderr or started.stdout or "").strip())
            return 1
        print("Gateway service started (systemd user).")
        return 0

    print(f"Gateway service start not supported on platform: {sys.platform}")
    return 1


def _stop_gateway_service() -> int:
    if _is_macos():
        domain = f"gui/{os.getuid()}"
        result = subprocess.run(
            ["launchctl", "bootout", f"{domain}/{GATEWAY_SERVICE_LABEL}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").lower()
            if "could not find service" in err or "no such process" in err:
                print("Gateway service already stopped (launchd).")
                return 0
            print((result.stderr or result.stdout or "").strip())
            return 1
        print("Gateway service stopped (launchd).")
        return 0

    if _is_linux():
        result = subprocess.run(
            ["systemctl", "--user", "stop", GATEWAY_SYSTEMD_SERVICE],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print((result.stderr or result.stdout or "").strip())
            return 1
        print("Gateway service stopped (systemd user).")
        return 0

    print(f"Gateway service stop not supported on platform: {sys.platform}")
    return 1


def _status_gateway_service() -> int:
    if _is_macos():
        domain = f"gui/{os.getuid()}"
        result = subprocess.run(
            ["launchctl", "print", f"{domain}/{GATEWAY_SERVICE_LABEL}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("Gateway service status: stopped")
            return 1
        print("Gateway service status: running (launchd)")
        return 0

    if _is_linux():
        active = subprocess.run(
            ["systemctl", "--user", "is-active", GATEWAY_SYSTEMD_SERVICE],
            capture_output=True,
            text=True,
        )
        status = (active.stdout or "").strip() or "inactive"
        print(f"Gateway service status: {status} (systemd user)")
        return 0 if active.returncode == 0 else 1

    print(f"Gateway service status not supported on platform: {sys.platform}")
    return 1


def _uninstall_gateway_service() -> int:
    _stop_gateway_service()
    if _is_macos():
        plist_path = _gateway_service_plist_path()
        if plist_path.exists():
            plist_path.unlink()
            print(f"Removed launchd service file: {plist_path}")
        else:
            print("Launchd service file already absent.")
        return 0

    if _is_linux():
        subprocess.run(["systemctl", "--user", "disable", GATEWAY_SYSTEMD_SERVICE], check=False)
        unit_path = _gateway_service_systemd_path()
        if unit_path.exists():
            unit_path.unlink()
            print(f"Removed systemd service file: {unit_path}")
        else:
            print("Systemd service file already absent.")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        return 0

    print(f"Gateway service uninstall not supported on platform: {sys.platform}")
    return 1


def _handle_gateway_service_action(action: str, workspace: str, host: str, port: int) -> int:
    normalized = (action or "").strip().lower()
    if normalized == "install":
        return _install_gateway_service(workspace, host, port)
    if normalized == "start":
        return _start_gateway_service()
    if normalized == "stop":
        return _stop_gateway_service()
    if normalized == "status":
        return _status_gateway_service()
    if normalized == "uninstall":
        return _uninstall_gateway_service()
    print("Usage: libre-claw --gateway-service [install|start|stop|status|uninstall]")
    return 1


def _run_doctor(config: Config, workspace_path: str, gateway_host: str, gateway_port: int) -> int:
    checks: list[tuple[str, str, str]] = []
    fatal_failures = 0

    def add_check(status: str, title: str, detail: str, fatal: bool = False) -> None:
        nonlocal fatal_failures
        checks.append((status, title, detail))
        if fatal and status == "FAIL":
            fatal_failures += 1

    workspace = Workspace(workspace_path, config)
    try:
        workspace.ensure_exists()
        probe = workspace.path / ".doctor-write-probe"
        probe.write_text("ok")
        probe.unlink(missing_ok=True)
        add_check("PASS", "workspace", f"accessible and writable: {workspace.path}", fatal=True)
    except Exception as e:
        add_check("FAIL", "workspace", f"not writable: {e}", fatal=True)

    interval = config.heartbeat.interval_seconds
    try:
        interval_value = int(interval)
    except Exception:
        interval_value = 0
    if interval_value > 0:
        add_check("PASS", "heartbeat.interval", f"{interval_value}s")
    else:
        add_check("FAIL", "heartbeat.interval", f"invalid interval: {interval}", fatal=True)

    heartbeat_path = workspace.path / "HEARTBEAT.md"
    if heartbeat_path.exists():
        add_check("PASS", "heartbeat.contract", "HEARTBEAT.md present")
    else:
        add_check("WARN", "heartbeat.contract", "HEARTBEAT.md missing")

    try:
        backend = get_backend(
            config.backend.type,
            BackendConfig(
                claude_path=config.backend.claude_path,
                codex_path=config.backend.codex_path,
                codex_model=config.backend.codex_model,
                openai_codex_auth_profiles_file=config.backend.openai_codex_auth_profiles_file,
                openai_codex_profile=config.backend.openai_codex_profile,
                openai_codex_model=config.backend.openai_codex_model,
                openai_codex_base_url=config.backend.openai_codex_base_url,
                anthropic_api_key=config.backend.anthropic_api_key,
                anthropic_auth_file=config.backend.anthropic_auth_file,
                anthropic_model=config.backend.anthropic_model,
                anthropic_base_url=config.backend.anthropic_base_url,
                openai_api_key=config.backend.openai_api_key,
                openai_auth_file=config.backend.openai_auth_file,
                openai_model=config.backend.openai_model,
                openai_base_url=config.backend.openai_base_url,
                ollama_url=config.backend.ollama_url,
                ollama_model=config.backend.ollama_model,
            ),
        )
        available = True
        if hasattr(backend, "check_available"):
            available = bool(backend.check_available())
        if available:
            add_check("PASS", "backend", f"{config.backend.type} available")
        else:
            add_check("FAIL", "backend", f"{config.backend.type} unavailable", fatal=True)
    except Exception as e:
        add_check("FAIL", "backend", f"backend init failed: {e}", fatal=True)

    gateway_url = (os.getenv("LIBRE_CLAW_GATEWAY_URL") or f"http://{gateway_host}:{gateway_port}").rstrip("/")
    try:
        with urllib.request.urlopen(f"{gateway_url}/gateway/status", timeout=1.5) as response:
            code = getattr(response, "status", 200)
            if 200 <= code < 500:
                add_check("PASS", "gateway", f"reachable at {gateway_url} (HTTP {code})")
            else:
                add_check("WARN", "gateway", f"reachable but unexpected HTTP {code}")
    except Exception as e:
        add_check("WARN", "gateway", f"not reachable at {gateway_url}: {e}")

    tool_mode = (os.getenv("LIBRE_CLAW_TOOL_MODE") or "local").strip().lower()
    if tool_mode in {"container", "docker", "sandbox"}:
        engine = (os.getenv("LIBRE_CLAW_CONTAINER_ENGINE") or "docker").strip() or "docker"
        resolved_engine = engine
        if not shutil.which(resolved_engine):
            if resolved_engine == "docker" and shutil.which("podman"):
                resolved_engine = "podman"
            else:
                add_check("FAIL", "container.runtime", f"{engine} not found in PATH", fatal=True)
                resolved_engine = ""
        if resolved_engine:
            add_check("PASS", "container.runtime", f"{resolved_engine} available (mode={tool_mode})")
    else:
        add_check("PASS", "container.runtime", f"mode={tool_mode}")

    print("Libre Claw doctor")
    print("")
    for status, title, detail in checks:
        marker = {
            "PASS": "[PASS]",
            "WARN": "[WARN]",
            "FAIL": "[FAIL]",
        }.get(status, "[INFO]")
        print(f"{marker} {title}: {detail}")
    print("")
    if fatal_failures:
        print(f"Doctor result: FAIL ({fatal_failures} fatal issue(s))")
        return 1
    print("Doctor result: PASS")
    return 0


def _run_onboard(config: Config, selected_workspace: str, gateway_host: str, gateway_port: int) -> int:
    print("Libre Claw onboarding")
    print("")

    default_workspace = str(Path(selected_workspace).expanduser().resolve())
    workspace_input = input(f"Workspace path [{default_workspace}]: ").strip()
    workspace_path = str(Path(workspace_input or default_workspace).expanduser().resolve())

    backend_default = config.backend.type
    backend_options = ["openai_codex", "openai", "anthropic", "ollama", "codex_cli", "claude_code"]
    print(f"Backend options: {', '.join(backend_options)}")
    backend_input = input(f"Backend [{backend_default}]: ").strip().lower()
    backend_choice = backend_input or backend_default
    if backend_choice not in backend_options:
        print(f"Invalid backend '{backend_choice}'.")
        return 1

    interval_default = str(config.heartbeat.interval_seconds)
    interval_input = input(f"Heartbeat interval (e.g. 30s, 5m) [{interval_default}]: ").strip()
    interval_value = interval_input or interval_default

    container_default = (os.getenv("LIBRE_CLAW_TOOL_MODE") or "local").strip().lower() in {"container", "docker", "sandbox"}
    container_choice = input(f"Use container tool mode? [{'Y' if container_default else 'n'}]: ").strip().lower()
    use_container = container_default if container_choice == "" else container_choice in {"y", "yes"}

    config.workspace.path = workspace_path
    config.backend.type = backend_choice
    config.heartbeat.enabled = True
    config.heartbeat.interval_seconds = interval_value

    workspace = Workspace(workspace_path, config)
    if not workspace.exists:
        workspace.init(force=False)
    config.save(workspace.path / "config.yaml")

    print("")
    print(f"Saved config: {workspace.path / 'config.yaml'}")
    print(f"Workspace ready: {workspace.path}")
    print(f"Backend: {config.backend.type}")
    print(f"Heartbeat interval: {config.heartbeat.interval_seconds}")
    if use_container:
        print("Container mode: enabled")
        print("Export before launch:")
        print("  export LIBRE_CLAW_TOOL_MODE=container")
        print("  export LIBRE_CLAW_CONTAINER_PERSISTENT=1")
    else:
        print("Container mode: local host execution")

    install_service = input("Install gateway user service now? [Y/n]: ").strip().lower()
    if install_service in {"", "y", "yes"}:
        code = _install_gateway_service(workspace_path, gateway_host, gateway_port)
        if code == 0:
            print("Run next: libre-claw --gateway-service start")
        return code

    return 0


def _self_update() -> int:
    cmd = [sys.executable, "-m", "pip", "install", "-U", "libre-claw"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print((result.stderr or result.stdout or "self-update failed").strip())
        return 1
    print("Self-update completed.")
    print((result.stdout or "").strip()[:1200])
    return 0


def _workspace_skills_root(workspace_path: str) -> Path:
    return Path(workspace_path).expanduser().resolve() / "skills"


def _managed_skills_root() -> Path:
    return Path.home() / ".libre-claw" / "skills"


def _looks_like_git_source(source: str) -> bool:
    value = (source or "").strip()
    return (
        value.startswith(("http://", "https://", "git@", "git+"))
        or value.endswith(".git")
        or ".git#" in value
    )


def _split_git_source(source: str) -> tuple[str, str]:
    value = (source or "").strip()
    if value.startswith("git+"):
        value = value[4:]
    if "#" not in value:
        return value, ""
    repo_url, subdir = value.split("#", 1)
    return repo_url.strip(), subdir.strip().strip("/")


def _load_curated_skills_catalog(workspace_path: str) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}

    def add_entries(entries: object) -> None:
        if not isinstance(entries, list):
            return
        for item in entries:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            source = str(item.get("source", "")).strip()
            if not name or not source:
                continue
            description = str(item.get("description", "")).strip()
            merged[name.lower()] = {
                "name": name,
                "source": source,
                "description": description,
            }

    add_entries(DEFAULT_CURATED_SKILLS)

    catalog_ref = (os.getenv("LIBRE_CLAW_SKILLS_CATALOG") or "").strip()
    if not catalog_ref:
        workspace_catalog = Path(workspace_path).expanduser().resolve() / "skills-catalog.json"
        if workspace_catalog.exists():
            catalog_ref = str(workspace_catalog)

    if catalog_ref:
        try:
            if catalog_ref.startswith(("http://", "https://")):
                with urllib.request.urlopen(catalog_ref, timeout=8) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            else:
                payload = json.loads(Path(catalog_ref).expanduser().read_text())

            if isinstance(payload, dict):
                payload = payload.get("skills", [])
            add_entries(payload)
        except Exception as exc:
            print(f"Warning: could not load curated skills catalog ({catalog_ref}): {exc}")

    return sorted(merged.values(), key=lambda x: x["name"].lower())


def _resolve_curated_skill(name_or_source: str, catalog: list[dict[str, str]]) -> dict[str, str] | None:
    probe = (name_or_source or "").strip().lower()
    for entry in catalog:
        if entry["name"].lower() == probe:
            return entry
    return None


def _copy_single_skill(source_dir: Path, root: Path, target_name: str | None = None) -> int:
    destination_name = (target_name or source_dir.name).strip()
    if not destination_name:
        print("Cannot determine skill destination name.")
        return 1
    target = root / destination_name
    if target.exists():
        print(f"Skill destination already exists: {target}")
        return 1
    shutil.copytree(source_dir, target)
    print(f"Installed skill: {target}")
    return 0


def _install_from_local_skill_path(src_path: Path, root: Path, preferred_name: str | None = None) -> int:
    if (src_path / "SKILL.md").exists():
        return _copy_single_skill(src_path, root, preferred_name)

    skill_dirs = [p for p in sorted(src_path.iterdir()) if p.is_dir() and (p / "SKILL.md").exists()]
    if not skill_dirs:
        print(f"No SKILL.md found at path: {src_path}")
        return 1

    installed = 0
    skipped = 0
    for skill_dir in skill_dirs:
        target = root / skill_dir.name
        if target.exists():
            print(f"Skipped existing skill: {target}")
            skipped += 1
            continue
        shutil.copytree(skill_dir, target)
        print(f"Installed skill: {target}")
        installed += 1

    if installed == 0:
        print("No skills installed; all destinations already existed.")
        return 1
    if skipped:
        print(f"Installed {installed} skill(s); skipped {skipped} existing.")
    return 0


def _install_from_git_skill_source(source: str, root: Path, preferred_name: str | None = None) -> int:
    repo_url, subdir = _split_git_source(source)
    if not repo_url:
        print(f"Invalid git source: {source}")
        return 1

    if not subdir:
        name = (preferred_name or Path(repo_url.rstrip("/")).name).strip()
        if name.endswith(".git"):
            name = name[:-4]
        target = root / name
        if target.exists():
            print(f"Skill destination already exists: {target}")
            return 1
        result = subprocess.run(["git", "clone", "--depth", "1", repo_url, str(target)], capture_output=True, text=True)
        if result.returncode != 0:
            print((result.stderr or result.stdout or "git clone failed").strip())
            return 1
        print(f"Installed skill repo: {target}")
        return 0

    tmp_dir = Path(tempfile.mkdtemp(prefix="libre-claw-skill-"))
    clone_dir = tmp_dir / "repo"
    try:
        result = subprocess.run(["git", "clone", "--depth", "1", repo_url, str(clone_dir)], capture_output=True, text=True)
        if result.returncode != 0:
            print((result.stderr or result.stdout or "git clone failed").strip())
            return 1

        source_dir = (clone_dir / subdir).resolve()
        try:
            source_dir.relative_to(clone_dir.resolve())
        except ValueError:
            print(f"Unsafe git subdir outside repo root: {subdir}")
            return 1

        if not source_dir.exists() or not source_dir.is_dir():
            print(f"Git subdir not found: {subdir}")
            return 1

        return _install_from_local_skill_path(source_dir, root, preferred_name=preferred_name)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _skills_list(workspace_path: str) -> int:
    roots = [
        ("workspace", _workspace_skills_root(workspace_path)),
        ("managed", _managed_skills_root()),
    ]
    any_found = False
    for label, root in roots:
        print(f"{label} skills: {root}")
        if not root.exists():
            print("  (none)")
            continue
        found = False
        for item in sorted(root.iterdir()):
            if item.is_dir():
                found = True
                any_found = True
                skill_md = item / "SKILL.md"
                marker = " (SKILL.md)" if skill_md.exists() else ""
                print(f"  - {item.name}{marker}")
        if not found:
            print("  (none)")
        print("")

    curated = _load_curated_skills_catalog(workspace_path)
    print("curated skills:")
    if not curated:
        print("  (none)")
    else:
        for entry in curated:
            desc = entry.get("description", "").strip()
            suffix = f" - {desc}" if desc else ""
            print(f"  - {entry['name']}{suffix}")
            print(f"    source: {entry['source']}")
    print("")

    return 0 if any_found else 0


def _skills_install(source: str, workspace_path: str) -> int:
    src = (source or "").strip()
    if not src:
        print("Usage: libre-claw --skills-install <curated-name|local-path-or-git-url>")
        return 1

    root = _workspace_skills_root(workspace_path)
    root.mkdir(parents=True, exist_ok=True)

    curated = _load_curated_skills_catalog(workspace_path)
    curated_match = _resolve_curated_skill(src, curated)
    preferred_name: str | None = None
    if curated_match:
        preferred_name = curated_match["name"]
        src = curated_match["source"]
        print(f"Resolved curated skill '{preferred_name}' -> {src}")

    if _looks_like_git_source(src):
        return _install_from_git_skill_source(src, root, preferred_name=preferred_name)

    src_path = Path(src).expanduser().resolve()
    if not src_path.exists() or not src_path.is_dir():
        print(f"Skill source path not found: {src_path}")
        return 1

    return _install_from_local_skill_path(src_path, root, preferred_name=preferred_name)


def main():
    """Main entry point for Libre Claw."""
    parser = argparse.ArgumentParser(
        description="Libre Claw - Agentic AI Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--config",
        "-c",
        help="Path to config file",
    )

    parser.add_argument(
        "--api",
        action="store_true",
        help="Start HTTP API server",
    )

    parser.add_argument(
        "--gateway",
        action="store_true",
        help="Start dedicated gateway server (autostarts proactive heartbeat loop)",
    )

    parser.add_argument(
        "--gateway-service",
        choices=["install", "start", "stop", "status", "uninstall"],
        help="Manage gateway as a user service (launchd on macOS, systemd --user on Linux)",
    )

    parser.add_argument(
        "--api-host",
        default="0.0.0.0",
        help="API server host",
    )

    parser.add_argument(
        "--api-port",
        type=int,
        default=8000,
        help="API server port",
    )

    parser.add_argument(
        "--gateway-host",
        default="127.0.0.1",
        help="Gateway server host (default: loopback)",
    )

    parser.add_argument(
        "--gateway-port",
        type=int,
        default=8421,
        help="Gateway server port",
    )

    parser.add_argument(
        "--workspace",
        "-w",
        help="Path to workspace directory",
    )

    parser.add_argument(
        "--backend",
        choices=["claude_code", "codex_cli", "openai_codex", "ollama", "anthropic", "openai"],
        help="Backend to use",
    )

    parser.add_argument(
        "--init",
        nargs="?",
        const=".",
        help="Initialize workspace at path",
    )

    parser.add_argument(
        "--heartbeat",
        action="store_true",
        help="Start with heartbeat enabled",
    )

    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run environment and configuration diagnostics",
    )

    parser.add_argument(
        "--onboard",
        action="store_true",
        help="Interactive onboarding wizard",
    )

    parser.add_argument(
        "--self-update",
        action="store_true",
        help="Upgrade libre-claw using pip",
    )

    parser.add_argument(
        "--skills-list",
        action="store_true",
        help="List installed skills plus curated catalog",
    )

    parser.add_argument(
        "--skills-install",
        help="Install a skill from curated name, local path, or git URL into workspace skills/",
    )

    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Disable git sync",
    )

    args = parser.parse_args()

    if args.self_update:
        exit_code = _self_update()
        if exit_code != 0:
            raise SystemExit(exit_code)
        return

    # Handle workspace initialization
    if args.init:
        init_path = Path(args.init).expanduser().resolve()
        workspace = Workspace(str(init_path))

        # Load config for git settings
        config = Config.load(args.config)
        if args.no_git:
            config.git.enabled = False

        workspace.config = config
        workspace.init(force=False)
        print(f"Initialized workspace at: {workspace.path}")
        return

    # Determine workspace path first (default: repo-local .workspace)
    cwd = Path.cwd().resolve()
    if cwd.name == ".workspace":
        default_workspace = str(cwd)
    else:
        default_workspace = str((cwd / ".workspace").resolve())
    selected_workspace = args.workspace or default_workspace

    if args.gateway_service:
        exit_code = _handle_gateway_service_action(
            args.gateway_service,
            str(Path(selected_workspace).expanduser().resolve()),
            args.gateway_host,
            int(args.gateway_port),
        )
        if exit_code != 0:
            raise SystemExit(exit_code)
        return

    if args.skills_list:
        exit_code = _skills_list(selected_workspace)
        if exit_code != 0:
            raise SystemExit(exit_code)
        return

    if args.skills_install:
        exit_code = _skills_install(args.skills_install, selected_workspace)
        if exit_code != 0:
            raise SystemExit(exit_code)
        return

    # Load configuration (workspace config takes precedence over global)
    config = Config.load(args.config, workspace_path=selected_workspace)

    # Override config with CLI args
    config.workspace.path = selected_workspace

    if args.backend:
        config.backend.type = args.backend
    else:
        # OpenClaw-like default: if Codex OAuth is active, use codex_cli automatically.
        try:
            codex_bin = config.backend.codex_path or "codex"
            status = subprocess.run([codex_bin, "login", "status"], capture_output=True, text=True, timeout=10)
            if status.returncode == 0:
                config.backend.type = "openai_codex"
        except Exception:
            pass

    if args.no_git:
        config.git.enabled = False

    # Ensure workspace exists and has baseline files/config
    ws = Workspace(config.workspace.path, config)
    if not ws.exists:
        ws.init(force=False)

    if args.doctor:
        exit_code = _run_doctor(config, selected_workspace, args.gateway_host, args.gateway_port)
        if exit_code != 0:
            raise SystemExit(exit_code)
        return

    if args.onboard:
        exit_code = _run_onboard(config, selected_workspace, args.gateway_host, args.gateway_port)
        if exit_code != 0:
            raise SystemExit(exit_code)
        return

    if args.gateway:
        # Start dedicated gateway server with proactive loop ownership
        app = create_app(
            config,
            gateway_mode=True,
            autostart_proactive=True,
        )
        uvicorn.run(
            app,
            host=args.gateway_host,
            port=args.gateway_port,
            log_level="info",
        )
    elif args.api:
        # Start API server
        app = create_app(config, gateway_mode=False, autostart_proactive=False)
        uvicorn.run(
            app,
            host=args.api_host,
            port=args.api_port,
            log_level="info",
        )
    else:
        # Start TUI
        backend = get_backend(
            config.backend.type,
            BackendConfig(
                claude_path=config.backend.claude_path,
                codex_path=config.backend.codex_path,
                codex_model=config.backend.codex_model,
                openai_codex_auth_profiles_file=config.backend.openai_codex_auth_profiles_file,
                openai_codex_profile=config.backend.openai_codex_profile,
                openai_codex_model=config.backend.openai_codex_model,
                openai_codex_base_url=config.backend.openai_codex_base_url,
                anthropic_api_key=config.backend.anthropic_api_key,
                anthropic_auth_file=config.backend.anthropic_auth_file,
                anthropic_model=config.backend.anthropic_model,
                anthropic_base_url=config.backend.anthropic_base_url,
                openai_api_key=config.backend.openai_api_key,
                openai_auth_file=config.backend.openai_auth_file,
                openai_model=config.backend.openai_model,
                openai_base_url=config.backend.openai_base_url,
                ollama_url=config.backend.ollama_url,
                ollama_model=config.backend.ollama_model,
            ),
        )

        workspace = ws
        memory = None
        if config.memory.enabled:
            memory = MemoryManager(config.memory.chromadb_url)

        agent = Agent(
            backend=backend,
            workspace=workspace,
            config=config,
            memory=memory,
        )

        # Start local proactive loop only when gateway is not reachable.
        gateway_url = (os.getenv("LIBRE_CLAW_GATEWAY_URL") or "http://127.0.0.1:8421").rstrip("/")
        gateway_reachable = False
        try:
            with urllib.request.urlopen(f"{gateway_url}/gateway/status", timeout=1.2) as resp:
                gateway_reachable = 200 <= getattr(resp, "status", 200) < 500
        except Exception:
            gateway_reachable = False

        force_local = (os.getenv("LIBRE_CLAW_FORCE_LOCAL_PROACTIVE") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if args.heartbeat or config.heartbeat.enabled:
            if gateway_reachable and not force_local:
                print(f"Gateway detected at {gateway_url}; using gateway proactive loop.")
            else:
                agent.start_proactive()

        start_tui(agent, config)


if __name__ == "__main__":
    main()
