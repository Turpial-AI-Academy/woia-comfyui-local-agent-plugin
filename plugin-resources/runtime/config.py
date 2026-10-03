"""Private configuration shared by the two local MCP processes.

``load_config`` returns Path objects for workspace, data_dir and comfy_bin;
server_url is a normalized string and user_id is None (default) or a string.
Reading configuration never creates directories or starts ComfyUI.
"""

from __future__ import annotations

import ipaddress
import json
import os
import sysconfig
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


class ConfigurationError(ValueError):
    """Configuration requires an explicit user or operator correction."""


def resolve_data_dir(value: Path | str | None = None) -> Path:
    raw = value if value is not None else os.environ.get("PLUGIN_DATA")
    if raw is None or not str(raw).strip():
        raise ConfigurationError("PLUGIN_DATA is missing; prepare this plugin's private runtime explicitly.")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ConfigurationError("PLUGIN_DATA must be an absolute path.")
    return path.resolve()


def normalize_server_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError("server_url must be an HTTP loopback URL with an explicit port.")
    try:
        url = urlsplit(value.strip())
        port = url.port
    except ValueError as exc:
        raise ConfigurationError("server_url contains an invalid host or port.") from exc
    host = url.hostname
    if url.scheme != "http" or not host:
        raise ConfigurationError("server_url must be an HTTP loopback URL with an explicit port; HTTPS is not supported by the pinned Comfy CLI.")
    if port is None or not 1 <= port <= 65535:
        raise ConfigurationError("server_url requires an explicit port from 1 through 65535 so both MCP servers use the same endpoint.")
    if url.username is not None or url.password is not None or url.query or url.fragment:
        raise ConfigurationError("server_url cannot contain credentials, query parameters or a fragment.")
    if url.path not in {"", "/"}:
        raise ConfigurationError("server_url must address the ComfyUI root, without a path prefix.")
    try:
        loopback = host.lower() == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        raise ConfigurationError("Only a loopback ComfyUI server is supported; no remote target is selected.")
    netloc = f"[{host}]" if ":" in host else host.lower()
    netloc += f":{port}"
    return urlunsplit((url.scheme, netloc, "", "", ""))


def validate_config(document: object, data_dir: Path) -> dict:
    if not isinstance(document, dict):
        raise ConfigurationError("config.json must contain an object.")
    permitted = {"schema_version", "server_url", "workspace", "user_id"}
    if set(document) - permitted:
        raise ConfigurationError("config.json contains unsupported fields.")
    if document.get("schema_version") != 1 or isinstance(document.get("schema_version"), bool):
        raise ConfigurationError("config.json requires schema_version 1.")
    raw_workspace = document.get("workspace")
    if not isinstance(raw_workspace, str) or not raw_workspace:
        raise ConfigurationError("workspace must be the absolute path of an existing ComfyUI core.")
    workspace = Path(raw_workspace).expanduser()
    if not workspace.is_absolute():
        raise ConfigurationError("workspace must be an absolute path.")
    workspace = workspace.resolve()
    # These are the file markers used by comfy-cli for portable/non-Git installs.
    markers = ("main.py", "comfy", "nodes.py", "comfy_extras", "comfy_api")
    recognized = sum((workspace / marker).exists() for marker in markers) >= 4
    if not workspace.is_dir() or not recognized or not (workspace / "main.py").is_file() or not (workspace / "nodes.py").is_file():
        raise ConfigurationError("workspace must contain the existing ComfyUI core (main.py and nodes.py).")
    user = document.get("user_id")
    if user is not None and (
        not isinstance(user, str) or not user or len(user) > 256 or any(ord(char) < 32 for char in user)
    ):
        raise ConfigurationError("user_id must be null for default or a nonempty valid ComfyUI user identifier.")
    scripts = Path(sysconfig.get_path("scripts")).resolve()
    return {
        "schema_version": 1,
        "server_url": normalize_server_url(document.get("server_url")),
        "workspace": workspace,
        "user_id": user,
        "data_dir": data_dir,
        "script_directory": scripts,
        "comfy_bin": scripts / ("comfy.exe" if os.name == "nt" else "comfy"),
    }


def load_config(data_dir: Path | None = None) -> dict:
    directory = resolve_data_dir(data_dir)
    target = directory / "config.json"
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError("Cannot read a valid private config.json; run prepare_runtime.py explicitly.") from exc
    return validate_config(document, directory)


def child_environment(config: dict, inherited: dict[str, str] | None = None) -> dict[str, str]:
    """Pin the local endpoint without altering the user's persistent settings.

    All inherited Comfy routing, consent, API credentials and project overrides
    are discarded. The official process remains unmodified, with its normal
    upstream tools; local-use limits are also stated in the capability skill.
    """
    source = os.environ if inherited is None else inherited
    env = {
        key: value for key, value in source.items()
        if not key.upper().startswith(("COMFY_", "COMFYUI_", "UV_"))
        and key.upper() not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"}
    }
    directory = config["data_dir"]
    env.update({
        "PLUGIN_DATA": str(directory),
        "UV_PROJECT_ENVIRONMENT": str(directory / "runtime"),
        "UV_CACHE_DIR": str(directory / "uv-cache"),
        "UV_PYTHON_DOWNLOADS": "never",
        "COMFY_BIN": str(config["comfy_bin"]),
        "COMFY_LOCAL_URL": config["server_url"],
        "COMFY_WHERE": "local",
        "COMFY_CACHE_DIR": str(directory / "comfy-cache"),
        "COMFY_NO_WATCH": "1",
        "COMFY_NO_TELEMETRY": "1",
        "COMFY_KNOWLEDGE_DISABLE": "1",
        "DO_NOT_TRACK": "1",
        "NO_PROXY": "127.0.0.1,localhost,::1",
        "no_proxy": "127.0.0.1,localhost,::1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return env
