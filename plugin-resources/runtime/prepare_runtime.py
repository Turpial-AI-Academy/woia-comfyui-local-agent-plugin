"""Explicit runtime preparation. Never called automatically by an MCP launcher."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from config import ConfigurationError, child_environment, resolve_data_dir, validate_config


PINNED = {"comfy-mcp": "0.10.0", "comfy-cli": "1.22.0", "mcp": "2.0.0"}


def atomic_json(path: Path, document: dict) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(document, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def inspect_python(python: Path) -> tuple[int, int]:
    if not python.is_absolute() or not python.is_file():
        raise ConfigurationError("--python must name an absolute existing Python executable.")
    probe = subprocess.run(
        [str(python), "-I", "-B", "-c", "import json,sys; print(json.dumps(list(sys.version_info[:2])))"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False, timeout=15,
    )
    try:
        version = tuple(json.loads(probe.stdout)) if probe.returncode == 0 else ()
    except (ValueError, TypeError):
        version = ()
    if len(version) != 2 or not (3, 10) <= version < (3, 15):
        raise ConfigurationError("--python must be an existing compatible Python 3.10 through 3.14. No interpreter will be installed.")
    return version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, help="Private plugin directory; defaults to PLUGIN_DATA.")
    parser.add_argument("--python", type=Path, required=True, help="Absolute path to an existing compatible Python.")
    parser.add_argument("--workspace", required=True, help="Existing ComfyUI core directory, not the Desktop binary directory.")
    parser.add_argument("--server-url", default="http://127.0.0.1:8188")
    parser.add_argument("--user-id", default=None, help="ComfyUI user identifier; omit for default.")
    args = parser.parse_args(argv)
    try:
        directory = resolve_data_dir(args.data_dir)
        document = {"schema_version": 1, "server_url": args.server_url, "workspace": args.workspace, "user_id": args.user_id}
        config = validate_config(document, directory)
        inspect_python(args.python)
        uv = shutil.which("uv")
        if uv is None:
            raise ConfigurationError("uv is not available. Install it explicitly before preparing this plugin.")
        # Validate before any writes. Preparation is the only dependency/network
        # boundary; no ComfyUI Python, models or global CLI defaults are changed.
        directory.mkdir(parents=True, exist_ok=True)
        env = child_environment(config)
        command = [uv, "sync", "--project", str(ROOT), "--frozen", "--no-python-downloads", "--python", str(args.python), "--default-index", "https://pypi.org/simple"]
        completed = subprocess.run(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=sys.stderr, stderr=sys.stderr, check=False)
        if completed.returncode:
            raise ConfigurationError(f"Explicit uv sync failed with exit {completed.returncode}; the runtime was not declared ready.")
        runtime_python = directory / "runtime" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        probe_code = "import importlib.metadata as m,json,sys; print(json.dumps({'python':list(sys.version_info[:3]),'distributions':{d.metadata['Name'].lower().replace('_','-'):d.version for d in m.distributions()}}))"
        probe = subprocess.run([str(runtime_python), "-I", "-B", "-c", probe_code], env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False, timeout=30)
        if probe.returncode:
            raise ConfigurationError("Could not inspect the newly prepared isolated interpreter.")
        info = json.loads(probe.stdout)
        if not all(info.get("distributions", {}).get(name) == version for name, version in PINNED.items()):
            raise ConfigurationError("Prepared dependency versions do not match the exact direct pins.")
        receipt = {
            "schema_version": 1, "status": "PREPARED", "prepared_at": datetime.now(timezone.utc).isoformat(),
            "python": info["python"], "distributions": info["distributions"],
            "payload_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ("pyproject.toml", "uv.lock")},
            "network_boundary": "Explicit uv sync using PyPI; no Python, models or ComfyUI dependencies acquired.",
        }
        # A successful explicit preparation may replace private configuration;
        # retain the exact previous config for recovery rather than discarding it.
        target = directory / "config.json"
        if target.exists() and target.read_bytes() != (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8"):
            backup = directory / "config-backups" / hashlib.sha256(target.read_bytes()).hexdigest()
            backup.parent.mkdir(exist_ok=True)
            if not backup.exists():
                backup.write_bytes(target.read_bytes())
        atomic_json(target, document)
        atomic_json(directory / "runtime-receipt.json", receipt)
        print(json.dumps({"status": "PREPARED", "server_url": config["server_url"], "data_dir": str(directory), "python": info["python"], "direct_dependencies": PINNED}))
        return 0
    except (ConfigurationError, OSError, subprocess.TimeoutExpired, ValueError) as exc:
        print(f"comfyui-local preparation: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
