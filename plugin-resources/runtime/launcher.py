"""Serve an explicitly prepared MCP runtime without installing or repairing it."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from config import ConfigurationError, child_environment, load_config


PINNED = {"comfy-mcp": "0.10.0", "comfy-cli": "1.22.0", "mcp": "2.0.0"}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_runtime(config: dict) -> dict:
    expected = (config["data_dir"] / "runtime").resolve()
    if Path(sys.prefix).resolve() != expected:
        raise ConfigurationError("Use the prepared PLUGIN_DATA/runtime interpreter through mcp.json; no global runtime is accepted.")
    if not (3, 10) <= sys.version_info[:2] < (3, 15):
        raise ConfigurationError("This locked runtime supports an existing Python 3.10 through 3.14.")
    try:
        receipt = json.loads((config["data_dir"] / "runtime-receipt.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError("No valid preparation receipt exists; run prepare_runtime.py explicitly. Startup will not download dependencies.") from exc
    if not isinstance(receipt, dict) or receipt.get("schema_version") != 1 or receipt.get("status") != "PREPARED":
        raise ConfigurationError("The runtime preparation receipt is invalid.")
    payload = receipt.get("payload_sha256")
    if not isinstance(payload, dict):
        raise ConfigurationError("The runtime preparation receipt is missing payload hashes.")
    for name in ("pyproject.toml", "uv.lock"):
        if payload.get(name) != file_sha256(ROOT / name):
            raise ConfigurationError("The runtime lock changed; explicitly prepare the runtime for this plugin version.")
    installed = receipt.get("distributions")
    if not isinstance(installed, dict) or not all(isinstance(name, str) and isinstance(version, str) for name, version in installed.items()) or not all(installed.get(name) == version for name, version in PINNED.items()):
        raise ConfigurationError("The preparation receipt does not cover the required pinned dependencies.")
    for name, version in installed.items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ConfigurationError(f"Runtime dependency {name} is missing; explicitly prepare again. No automatic repair was attempted.") from exc
        if actual != version:
            raise ConfigurationError(f"Runtime dependency {name} differs from the prepared lock; explicitly prepare again.")
    if not config["comfy_bin"].is_file():
        raise ConfigurationError("The prepared comfy CLI executable is missing; explicitly prepare again.")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("server", choices=("official", "companion"))
    args = parser.parse_args(argv)
    try:
        config = load_config()
        check_runtime(config)
        env = child_environment(config)
        if args.server == "official":
            command = [sys.executable, "-B", "-m", "comfy_mcp.server"]
        else:
            companion = ROOT / "companion.py"
            if not companion.is_file():
                raise ConfigurationError("The companion MCP entrypoint is missing from this plugin package.")
            command = [sys.executable, "-B", str(companion)]
        # The official server is run as the upstream module in a separate
        # executable process; no upstream classes, tools or instructions change.
        # Keep this launcher alive until its child exits on Windows as well as
        # POSIX. Inheriting all three streams preserves the stdio protocol.
        completed = subprocess.run(command, cwd=config["workspace"], env=env, check=False)
        return completed.returncode
    except (ConfigurationError, OSError) as exc:
        print(f"comfyui-local: {exc}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
