"""MIT domain operations for the local ComfyUI companion.

The official CLI remains a subprocess dependency. No upstream implementation
is imported or copied here. This module never launches ComfyUI, submits prompts,
installs nodes or models, cancels jobs, or invokes a shell.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import mimetypes
import os
import re
import stat
import subprocess
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class CompanionError(ValueError):
    """A scoped operation failed without implying permission to repair it."""


MAX_DOCUMENT = 16 * 1024 * 1024
MAX_RESPONSE = 64 * 1024 * 1024
MAX_ASSET = 512 * 1024 * 1024
MAX_OUTPUT = 2 * 1024 * 1024 * 1024
MAX_FILES = 2000
MAX_ENTRIES = 4000
MAX_DEPTH = 16
_SERIAL = threading.RLock()
_SHA = re.compile(r"^[a-fA-F0-9]{64}$")
_RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)
_OPS = {"add_node", "connect", "set_widget", "set_node_field", "delete_node"}
_SAMPLERS = {"KSampler", "KSamplerAdvanced", "SamplerCustom", "SamplerCustomAdvanced"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_bytes(value: Any) -> bytes:
    try:
        data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CompanionError("value must be finite JSON") from exc
    if len(data) > MAX_DOCUMENT:
        raise CompanionError("document exceeds the 16 MiB limit")
    return data


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expected(value: str | None) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise CompanionError("expected_sha256 must be the reviewed current SHA-256")
    return value.lower()


def _relative(value: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not allow_empty):
        raise CompanionError("a nonempty project-relative path is required")
    if value == "" and allow_empty:
        return ""
    if "\\" in value or "%" in value or any(ord(c) < 32 for c in value):
        raise CompanionError("paths must use literal forward slashes without encoded or control characters")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(p in {"", ".", ".."} for p in value.split("/")):
        raise CompanionError("path must be a normalized relative path without traversal")
    for part in path.parts:
        if any(c in part for c in ':*?"<>|') or part.endswith((".", " ")) or _RESERVED.match(part):
            raise CompanionError("path contains a nonportable filename")
    return value


def _server_relative(value: str, *, allow_empty: bool = False) -> str:
    """Normalize only server-provided Windows separators, then apply path guards."""
    if not isinstance(value, str):
        raise CompanionError("server-relative paths must be strings")
    return _relative(value.replace("\\", "/"), allow_empty=allow_empty)


def _reference_normalization(literal: dict, normalized: dict) -> dict:
    return {key: "unchanged" if literal[key] == normalized[key] else "windows_separators_to_forward_slashes" for key in literal if key != "type"}


def _asset_upload_name(root: Path, relative: str, content_sha256: str) -> tuple[str, str]:
    """A portable root filename that keeps project/path/content identity separate."""
    project_id = _sha(str(root).encode("utf-8"))[:16]
    asset_id = _sha(relative.encode("utf-8"))[:16]
    prefix = f"comfyui-local-{project_id}-{asset_id}-{content_sha256[:16]}-"
    basename = PurePosixPath(relative).name
    stem, suffix = Path(basename).stem, Path(basename).suffix
    # Leave room for backend collision suffixes and stay below both POSIX-byte
    # and Windows UTF-16 component limits without splitting a Unicode character.
    while len((prefix + stem + suffix).encode("utf-8")) > 200:
        if not stem:
            raise CompanionError("asset extension is too long for a portable upload filename")
        stem = stem[:-1]
    if not stem:
        raise CompanionError("asset name is too long for a portable upload filename")
    return prefix + stem + suffix, prefix


def _no_links(path: Path) -> None:
    """Inspect existing ancestors without following symlinks or Windows reparse points."""
    for item in reversed((path, *path.parents)):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise CompanionError(f"symlink/reparse paths are not allowed: {item}")


def _absolute(value: str | Path, *, exists: bool = True) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or path.anchor.startswith("\\\\"):
        raise CompanionError("project_root must be an absolute local path without traversal")
    _no_links(path)
    if exists and not path.is_dir():
        raise CompanionError(f"directory does not exist: {path}")
    return path


def _under(root: Path, name: str, *, exists: bool = False) -> Path:
    relative = _relative(name)
    target = root.joinpath(*PurePosixPath(relative).parts)
    _no_links(target)
    if not target.resolve().is_relative_to(root.resolve()):
        raise CompanionError("path escapes the project")
    if exists and not target.is_file():
        raise CompanionError(f"file does not exist: {relative}")
    return target


def _read(path: Path, maximum: int = MAX_DOCUMENT) -> bytes:
    _no_links(path)
    if not path.is_file():
        raise CompanionError(f"file does not exist: {path.name}")
    with path.open("rb") as handle:
        data = handle.read(maximum + 1)
    if len(data) > maximum:
        raise CompanionError(f"file exceeds the {maximum} byte limit")
    return data


def _create(path: Path, data: bytes) -> None:
    _no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _no_links(path)
    owned = False
    try:
        with path.open("xb") as handle:
            owned = True
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise CompanionError(f"collision: destination already exists: {path.name}") from exc
    except Exception:
        if owned:
            path.unlink(missing_ok=True)
        raise


def _managed_replace(path: Path, data: bytes, before: bytes | None) -> None:
    """Replace companion-owned mapping state after an optimistic conflict check."""
    if before is None:
        _create(path, data)
        return
    _no_links(path)
    fd, name = tempfile.mkstemp(prefix=".companion-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if _read(path) != before:
            raise CompanionError("managed state changed; preserve both states and retry after review")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _workflow(data: Any) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
        raise CompanionError("a complete visual workflow with nodes[] is required; API prompts belong to the official MCP")
    if "links" in data and not isinstance(data["links"], list):
        raise CompanionError("visual workflow links must be a list")
    _json_bytes(data)
    return data


def _parse_json(data: bytes, label: str) -> Any:
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise CompanionError(f"{label} is not UTF-8 JSON") from exc


def _visual_node(document: dict, path: tuple[str, ...]) -> dict | None:
    """Resolve an effective receipt path in the resulting visual document."""
    if not path or len(path) > MAX_DEPTH:
        raise CompanionError("CLI widget receipt has an invalid node path")
    definitions = (document.get("definitions") or {}).get("subgraphs") or []
    if not isinstance(definitions, list):
        raise CompanionError("subgraph definitions must be a list")
    scope = document
    for index, identifier in enumerate(path):
        matches = [node for node in scope.get("nodes", []) if isinstance(node, dict) and str(node.get("id")) == identifier]
        if not matches:
            return None  # A later operation may have deleted the edited node.
        if len(matches) != 1:
            raise CompanionError("ambiguous effective node in CLI widget receipt")
        node = matches[0]
        if index == len(path) - 1:
            return node
        candidates = [item for item in definitions if isinstance(item, dict) and item.get("id") == node.get("type")]
        if not candidates:
            candidates = [item for item in definitions if isinstance(item, dict) and item.get("name") == node.get("type")]
        if len(candidates) != 1:
            raise CompanionError("effective CLI widget path has an unresolved or ambiguous subgraph")
        scope = candidates[0]
    return None


def _reconcile_named_widgets(document: dict, payload: dict, source: dict, slots_reader) -> list[dict]:
    """Keep existing named serialization coherent with actual CLI widget writes.

    The CLI's full receipt supplies effective targets and normalized values;
    positional arrays stay authoritative and untouched here. A rebuilt dynamic
    roster is inspected through CLI slots rather than guessed from array order.
    """
    applied = payload.get("ops")
    if not isinstance(applied, list) or payload.get("count") != len(applied):
        raise CompanionError("CLI full edit receipt is missing; source preserved")
    touched: dict[tuple[str, ...], set[str]] = {}
    dynamic: set[tuple[tuple[str, ...], str]] = set()
    writes: list[tuple[tuple[str, ...], str, dict, list]] = []
    effective_controls: set[tuple[tuple[str, ...], str]] = set()
    for operation in applied:
        if not isinstance(operation, dict):
            raise CompanionError("CLI full edit receipt contains an invalid operation")
        if operation.get("op") != "set_widget":
            continue
        promoted = operation.get("promoted") or {}
        segments = promoted.get("instance_path") or operation.get("path") or [operation.get("node_id")]
        if not isinstance(segments, list) or any(item is None for item in segments):
            raise CompanionError("CLI widget receipt lacks its effective node path")
        path = tuple(str(item) for item in segments)
        widget = operation.get("inner_widget") if operation.get("path") else operation.get("widget")
        if not isinstance(widget, str) or not widget or "value" not in operation:
            raise CompanionError("CLI widget receipt lacks its canonical widget value")
        warnings = operation.get("warnings") or []
        if any(isinstance(warning, dict) and warning.get("code") == "unknown_dynamic_sub_input" for warning in warnings):
            raise CompanionError("CLI did not write an unsupported dynamic sub-input; entire derived revision discarded, source preserved")
        control = (path, widget)
        if control in effective_controls:
            raise CompanionError("repeated effective widget target in one batch; use one write per control; entire derived revision discarded, source preserved")
        effective_controls.add(control)
        writes.append((path, widget, operation, warnings))
    # Validate all effective destinations before touching either serialization.
    # CLI LWW can reject a later duplicate even when it appears in the receipt.
    for path, widget, operation, warnings in writes:
        node = _visual_node(document, path)
        if node is None or "widgets_values_named" not in node:
            continue  # Positional-only documents keep their established format.
        named = node["widgets_values_named"]
        if not isinstance(named, dict):
            raise CompanionError("edited node has invalid named-widget serialization")
        named[widget] = operation["value"]
        touched.setdefault(path, set()).add(widget)
        if any(isinstance(warning, dict) and warning.get("code") == "dynamic_combo_roster_rebuilt" for warning in warnings):
            dynamic.add((path, widget))
    if dynamic:
        old_slots = slots_reader(source, "before")
        new_slots = slots_reader(document, "after")
        for path, selector in sorted(dynamic, key=lambda item: (item[0], item[1].count("."), item[1])):
            node = _visual_node(document, path)
            if node is None:
                continue
            address = "/".join(path)
            prefix = selector + "."
            prior_names = {slot.get("name") for slot in old_slots if isinstance(slot, dict) and slot.get("instance_id") == address and isinstance(slot.get("name"), str) and slot["name"].startswith(prefix)}
            prior_names.update(name for name in touched[path] if name.startswith(prefix))
            current = {slot["name"]: slot.get("current_value") for slot in new_slots if isinstance(slot, dict) and slot.get("instance_id") == address and isinstance(slot.get("name"), str) and (slot["name"] == selector or slot["name"].startswith(prefix))}
            if selector not in current:
                if any(parent_path == path and selector.startswith(parent_selector + ".") for parent_path, parent_selector in dynamic):
                    continue  # A later ancestor selector legitimately removed this sub-roster.
                raise CompanionError("CLI slots could not resolve a rebuilt selector; source preserved")
            named = node["widgets_values_named"]
            for inactive in prior_names - current.keys():
                named.pop(inactive, None)
                touched[path].add(inactive)
            for name, value in current.items():
                named[name] = value
                touched[path].add(name)
    return [{"node_path": list(path), "widgets": sorted(names)} for path, names in sorted(touched.items())]


def _compact_edit_receipt(payload: dict, reconciled: list[dict]) -> dict:
    applied = payload["ops"]
    kinds: dict[str, int] = {}
    for operation in applied:
        kind = operation["op"]
        kinds[kind] = kinds.get(kind, 0) + 1
    writes = []
    warnings = []
    for operation in applied:
        warnings.extend(operation.get("warnings") or [])
        if operation.get("op") == "set_widget":
            promoted = operation.get("promoted") or {}
            path = promoted.get("instance_path") or operation.get("path") or [operation["node_id"]]
            widget = operation["inner_widget"] if operation.get("path") else operation["widget"]
            writes.append({"node_path": [str(item) for item in path], "widget": widget, "value": operation["value"]})
    receipt = {"count": payload["count"], "ops_by_kind": kinds, "nodes_added": [item["node_id"] for item in applied if item["op"] == "add_node"], "nodes_deleted": [item["node_id"] for item in applied if item["op"] == "delete_node"], "aliases": payload.get("aliases") or {}, "widget_writes": writes, "warnings": warnings, "named_widgets_reconciled": reconciled}
    for field in ("base_version", "version", "changed"):
        if field in payload:
            receipt[field] = payload[field]
    return receipt


def _project_config(root: Path) -> dict:
    marker = _under(root, "comfy.yaml", exists=True)
    raw = _read(marker)
    try:
        parsed = json.loads(raw)
    except ValueError:
        try:
            import yaml
        except ImportError as exc:
            raise CompanionError("YAML support is missing from the prepared runtime") from exc
        parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict) or parsed.get("schema") != "project/1":
        raise CompanionError("project_root must itself contain a comfy.yaml marker with schema project/1")
    return parsed


def _project(value: str) -> Path:
    root = _absolute(value)
    _project_config(root)
    for name in ("assets", "fragments", "blueprints", "outputs", ".comfy"):
        _no_links(root / name)
    return root


@contextmanager
def _project_lock(root: Path):
    with _SERIAL:
        lock = _under(root, ".comfy/companion.lock")
        token = _json_bytes({"pid": os.getpid(), "token": uuid.uuid4().hex, "at": _now()})
        try:
            _create(lock, token)
        except CompanionError as exc:
            raise CompanionError("project is locked by another operation; inspect its owner instead of deleting the lock") from exc
        try:
            yield
        finally:
            if _read(lock) == token:
                lock.unlink()


def _files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    _no_links(root)
    found: list[Path] = []
    entries = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        entries += len(dirs) + len(files)
        if entries > MAX_ENTRIES or len(Path(directory).relative_to(root).parts) > MAX_DEPTH:
            raise CompanionError("inventory budget exceeded; narrow the requested directory")
        for name in dirs + files:
            _no_links(Path(directory) / name)
        for name in files:
            found.append(Path(directory) / name)
            if len(found) > MAX_FILES:
                raise CompanionError(f"inventory exceeds {MAX_FILES} files; narrow the requested directory")
    return sorted(found)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CompanionError("redirects are disabled for local ComfyUI requests")


class LocalHttp:
    def __init__(self, url: str, user_id: str | None):
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise CompanionError("server_url contains an invalid host or port") from exc
        try:
            loopback = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname or "").is_loopback
        except ValueError:
            loopback = False
        if parsed.scheme != "http" or not loopback or port is None or not 1 <= port <= 65535:
            raise CompanionError("server_url must identify an HTTP loopback ComfyUI endpoint with an explicit valid port")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise CompanionError("server_url must not contain credentials, query parameters, or a path")
        self.url = url.rstrip("/")
        self.user_id = user_id or "default"
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.user_id):
            raise CompanionError("user_id contains invalid header characters")
        # Local traffic must never be forwarded through inherited HTTP proxies.
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _request(self, method: str, path: str, data: bytes | None = None, content_type: str = "application/json") -> Request:
        if not path.startswith("/") or path.startswith("//") or "\r" in path or "\n" in path:
            raise CompanionError("invalid local HTTP route")
        return Request(self.url + path, data=data, method=method, headers={"Comfy-User": self.user_id, "Content-Type": content_type})

    def bytes(self, method: str, path: str, data: bytes | None = None, *, content_type: str = "application/json", allow_missing: bool = False) -> bytes | None:
        request = self._request(method, path, data, content_type)
        try:
            with self.opener.open(request, timeout=30) as response:
                body = response.read(MAX_RESPONSE + 1)
                if len(body) > MAX_RESPONSE:
                    raise CompanionError("local HTTP response exceeds the bounded response limit")
                return body
        except HTTPError as exc:
            if allow_missing and exc.code == 404:
                return None
            raise CompanionError(f"ComfyUI returned HTTP {exc.code} for {method} {path.split('?')[0]}; no retry or fallback was performed") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise CompanionError(f"local ComfyUI request failed: {type(exc).__name__}; no launch, resubmission, or cancellation was performed") from exc

    def json(self, method: str, path: str, data: Any = None, *, allow_missing: bool = False) -> Any:
        result = self.bytes(method, path, _json_bytes(data) if data is not None else None, allow_missing=allow_missing)
        return None if result is None else _parse_json(result, "ComfyUI response")

    def profile(self) -> dict:
        users = self.json("GET", "/users")
        if not isinstance(users, dict):
            raise CompanionError("ComfyUI /users returned an unexpected profile description")
        if isinstance(users.get("users"), dict):
            if self.user_id not in users["users"]:
                raise CompanionError("configured user_id is absent from this multi-user server; no default-user fallback")
            return {"user_id": self.user_id, "multi_user": True}
        if self.user_id != "default":
            raise CompanionError("an explicit non-default user_id requires a multi-user server")
        return {"user_id": "default", "multi_user": False}

    def download(self, route: str, destination: Path) -> dict:
        _no_links(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        _no_links(destination)
        digest = hashlib.sha256()
        size = 0
        owned = False
        try:
            with self.opener.open(self._request("GET", route), timeout=30) as response, destination.open("xb") as output:
                owned = True
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > MAX_OUTPUT:
                        raise CompanionError("output exceeds the 2 GiB per-file recording limit")
                    digest.update(chunk)
                    output.write(chunk)
                content_type = response.headers.get("Content-Type", "application/octet-stream")
        except Exception as exc:
            if owned:
                destination.unlink(missing_ok=True)
            if isinstance(exc, CompanionError):
                raise
            raise CompanionError("output transfer failed; no generation was resubmitted") from exc
        if not size:
            destination.unlink()
            raise CompanionError("server returned an empty output file")
        return {"path": str(destination), "bytes": size, "sha256": digest.hexdigest(), "content_type": content_type, "decode_review": "NOT_RUN"}


class Companion:
    """Seven project-scoped operations; configuration is supplied by the launcher."""

    def __init__(self, config: dict):
        self.config = config
        self.http = LocalHttp(config["server_url"], config.get("user_id"))

    def local_status(self) -> dict:
        return {"server_url": self.http.url, "profile": self.http.profile(), "system_stats": self.http.json("GET", "/system_stats"), "queue": self.http.json("GET", "/queue"), "model_execution": "NOT_RUN", "capability_discovery": "query the official MCP node/model inventory"}

    def project(self, action: str, project_root: str) -> dict:
        if action == "list":
            root = _absolute(project_root)
            projects = []
            for count, entry in enumerate(sorted(root.iterdir()), 1):
                if count > MAX_ENTRIES:
                    raise CompanionError("project collection inventory budget exceeded; narrow the collection root")
                if len(projects) >= 200:
                    raise CompanionError("project list exceeds 200 entries; narrow the collection root")
                _no_links(entry)
                if entry.is_dir() and (entry / "comfy.yaml").exists():
                    try:
                        marker = _project_config(entry)
                    except CompanionError:
                        continue
                    projects.append({"project_root": str(entry), "schema": marker["schema"]})
            return {"collection_root": str(root), "projects": projects}
        if action == "create":
            root = _absolute(project_root, exists=False)
            for ancestor in (root, *root.parents):
                if (ancestor / "comfy.yaml").exists():
                    raise CompanionError(f"a marker already exists at {ancestor}; nested or ancestor reinitialization is refused")
            if root.exists() and (not root.is_dir() or any(root.iterdir())):
                raise CompanionError("create requires a new or empty project directory")
            root.mkdir(parents=True, exist_ok=True)
            _create(root / "comfy.yaml", _json_bytes({"schema": "project/1", "defaults": {"where": "local"}}))
            for name in ("assets", "fragments", "blueprints", "outputs", ".comfy"):
                (root / name).mkdir(exist_ok=True)
        elif action != "status":
            raise CompanionError("project action must be list, create, or status")
        root = _project(project_root)
        return {"project_root": str(root), "schema": "project/1", "config": _project_config(root), "workflows": [p.relative_to(root).as_posix() for p in _files(root / "blueprints") if p.suffix.lower() == ".json"], "assets": [p.relative_to(root / "assets").as_posix() for p in _files(root / "assets")], "runs": [p.relative_to(root).as_posix() for p in _files(root / ".comfy" / "recorded-runs") if p.name == "record.json"]}

    def workflow_document(self, action: str, project_root: str, path: str, document: dict | None = None, source_path: str | None = None) -> dict:
        root = _project(project_root)
        target = _under(root, path)
        if target.suffix.lower() != ".json":
            raise CompanionError("visual workflow documents must use .json")
        if action == "read":
            raw = _read(target)
            return {"path": str(target), "sha256": _sha(raw), "document": _workflow(_parse_json(raw, "workflow"))}
        if action not in {"create", "copy"}:
            raise CompanionError("workflow_document action must be read, create, or copy")
        with _project_lock(root):
            if action == "copy":
                if not source_path or document is not None:
                    raise CompanionError("copy requires source_path and no document")
                raw = _read(_under(root, source_path, exists=True))
                _workflow(_parse_json(raw, "source workflow"))
            else:
                if document is None or source_path is not None:
                    raise CompanionError("create requires a document and no source_path")
                raw = _json_bytes(_workflow(document))
            _create(target, raw)
        return {"path": str(target), "sha256": _sha(raw), "action": action, "created": True}

    def workflow_edit(self, project_root: str, path: str, operations: list[dict], expected_sha256: str, output_path: str | None = None) -> dict:
        root = _project(project_root)
        source = _under(root, path, exists=True)
        if not isinstance(operations, list) or not operations or len(operations) > 200:
            raise CompanionError("operations must contain 1 to 200 edits")
        if any(not isinstance(op, dict) or op.get("op") not in _OPS for op in operations):
            raise CompanionError("allowed edits: add_node, connect, set_widget, set_node_field, delete_node")
        _json_bytes(operations)
        destination = _under(root, output_path or f"{source.relative_to(root).with_suffix('').as_posix()}.revision-{uuid.uuid4().hex[:12]}.json")
        if destination == source or destination.exists():
            raise CompanionError("workflow_edit creates a distinct new revision; destination already exists or equals its source")
        if destination.suffix.lower() != ".json":
            raise CompanionError("revision must use .json")
        executable = Path(self.config["comfy_bin"])
        if not executable.is_absolute() or not executable.is_file():
            raise CompanionError("prepared comfy CLI executable is missing; run the explicit runtime preparation procedure")
        parsed = urlsplit(self.http.url)
        with _project_lock(root):
            before = _read(source)
            if _sha(before) != _expected(expected_sha256):
                raise CompanionError("source SHA-256 changed; review the current workflow before editing")
            source_document = _workflow(_parse_json(before, "source workflow"))
            # Use a private immutable input copy: the CLI cannot overwrite the source.
            temporary_root = _under(root, f".comfy/edit-{uuid.uuid4().hex}")
            temporary_root.mkdir()
            temporary_input = temporary_root / "source.json"
            catalog_input = temporary_root / "object_info.json"
            slots_input = temporary_root / "slots.json"
            _create(temporary_input, before)
            try:
                # Fresh schemas are fetched with the selected Comfy-User header.
                # --input disables CLI cache/cloud discovery and its user-header gap.
                catalog = self.http.json("GET", "/object_info")
                if not isinstance(catalog, dict):
                    raise CompanionError("ComfyUI object_info must be a node-schema object")
                catalog_bytes = json.dumps(catalog, ensure_ascii=False, allow_nan=False).encode("utf-8")
                _create(catalog_input, catalog_bytes)
                command = [str(executable), "--json", "workflow", "apply", str(temporary_input), "--ops", "-", "--stdout", "--ack", "full", "--where", "local", "--input", str(catalog_input), "--host", parsed.hostname or "127.0.0.1", "--port", str(parsed.port)]
                try:
                    from config import child_environment
                    environment = child_environment(self.config)
                    environment["COMFY_PROJECT"] = str(root)
                    result = subprocess.run(command, input=json.dumps(operations, ensure_ascii=False, allow_nan=False), capture_output=True, text=True, encoding="utf-8", cwd=root, shell=False, timeout=90, env=environment)
                except subprocess.TimeoutExpired as exc:
                    raise CompanionError("CLI edit timed out; source preserved, no generation was submitted") from exc
                try:
                    envelope = json.loads(result.stdout)
                except ValueError as exc:
                    raise CompanionError("CLI edit did not return its JSON envelope; source preserved") from exc
                if result.returncode != 0 or not isinstance(envelope, dict) or not envelope.get("ok"):
                    error = envelope.get("error") if isinstance(envelope, dict) else None
                    raise CompanionError(f"CLI edit rejected the batch; source preserved: {error}")
                payload = envelope.get("data") or {}
                updated = _workflow(payload.get("workflow_json"))
                def read_slots(document: dict, label: str) -> list:
                    _create(slots_input, _json_bytes(document))
                    try:
                        slots_command = [str(executable), "--json", "workflow", "slots", str(slots_input), "--input", str(catalog_input)]
                        try:
                            slots_result = subprocess.run(slots_command, capture_output=True, text=True, encoding="utf-8", cwd=root, shell=False, timeout=90, env=environment)
                        except subprocess.TimeoutExpired as exc:
                            raise CompanionError(f"CLI {label} widget inspection timed out; source preserved") from exc
                        try:
                            slots_envelope = json.loads(slots_result.stdout)
                        except ValueError as exc:
                            raise CompanionError("CLI widget inspection did not return JSON; source preserved") from exc
                        slots = (slots_envelope.get("data") or {}).get("slots") if isinstance(slots_envelope, dict) else None
                        if slots_result.returncode != 0 or not slots_envelope.get("ok") or not isinstance(slots, list):
                            raise CompanionError("CLI widget inspection failed; source preserved")
                        return slots
                    finally:
                        slots_input.unlink(missing_ok=True)
                reconciled = _reconcile_named_widgets(updated, payload, source_document, read_slots)
                receipt = _compact_edit_receipt(payload, reconciled)
                if _read(source) != before:
                    raise CompanionError("source changed during editing; no revision was saved")
                raw = _json_bytes(updated)
                _create(destination, raw)
            finally:
                temporary_input.unlink(missing_ok=True)
                catalog_input.unlink(missing_ok=True)
                slots_input.unlink(missing_ok=True)
                temporary_root.rmdir()
        return {"path": str(destination), "sha256": _sha(raw), "source_path": str(source), "source_sha256": _sha(before), "cli_receipt": receipt, "source_preserved": True, "model_execution": "NOT_RUN"}

    def workflow_store(self, action: str, project_root: str, name: str | None = None, path: str | None = None, replace: bool = False, expected_sha256: str | None = None) -> dict:
        root = _project(project_root)
        profile = self.http.profile()
        if action == "list":
            files = self.http.json("GET", "/userdata?" + urlencode({"dir": "workflows", "recurse": "true", "full_info": "true"}), allow_missing=True)
            return {"profile": profile, "files": files or []}
        if not name:
            raise CompanionError("workflow name is required")
        name = _relative(name)
        if not name.endswith(".json"):
            raise CompanionError("stored visual workflows must use a .json name")
        route = "/userdata/" + quote("workflows/" + name, safe="")
        if action == "get":
            raw = self.http.bytes("GET", route)
            result = {"profile": profile, "name": name, "sha256": _sha(raw), "document": _workflow(_parse_json(raw, "stored workflow"))}
            if path:
                target = _under(root, path)
                with _project_lock(root):
                    _create(target, raw)
                result["path"] = str(target)
            return result
        if action not in {"save", "delete"}:
            raise CompanionError("workflow_store action must be list, get, save, or delete")
        if action == "delete" and (not replace or path is not None):
            raise CompanionError("delete requires replace=true as explicit mutation intent, no path, and expected_sha256")
        if action == "save" and not path:
            raise CompanionError("save requires a project-relative visual workflow path")
        with _project_lock(root):
            source = _read(_under(root, path, exists=True)) if action == "save" else None
            if source is not None:
                _workflow(_parse_json(source, "workflow"))
            before = self.http.bytes("GET", route, allow_missing=True)
            backup = None
            if before is not None:
                if not replace:
                    raise CompanionError("workflow already exists; use a new name or request replacement with its current SHA-256")
                if _sha(before) != _expected(expected_sha256):
                    raise CompanionError("stored workflow SHA-256 changed; no mutation performed")
                backup = _under(root, f".comfy/backups/workflow-{uuid.uuid4().hex}.json")
                _create(backup, before)
                if self.http.bytes("GET", route) != before:
                    raise CompanionError("stored workflow changed after backup; mutation refused and backup retained")
            elif replace or action == "delete":
                raise CompanionError("requested existing workflow was not found; no create fallback")
            if action == "delete":
                self.http.bytes("DELETE", route)
                if self.http.bytes("GET", route, allow_missing=True) is not None:
                    raise CompanionError("deletion could not be confirmed; inspect the retained backup")
                return {"profile": profile, "name": name, "deleted": True, "backup_path": str(backup), "backup_sha256": _sha(before), "concurrency": "optimistic hash check; ComfyUI userdata has no atomic compare-and-swap"}
            query = urlencode({"overwrite": "true" if replace else "false", "full_info": "true"})
            self.http.bytes("POST", route + "?" + query, source)
            actual = self.http.bytes("GET", route)
            if actual != source:
                raise CompanionError("saved bytes differ from the source; do not retry silently; inspect the server and retained backup")
        return {"profile": profile, "name": name, "sha256": _sha(actual), "saved": True, "replaced": replace, "backup_path": str(backup) if backup else None, "desktop": "open this workflow from Workflows; an already-open canvas was not modified", "concurrency": "create-only by default; replacements use optimistic hash checks, not server-side compare-and-swap"}

    def project_assets(self, action: str, project_root: str, asset_path: str | None = None) -> dict:
        root = _project(project_root)
        assets = root / "assets"
        if action == "list":
            return {"project_root": str(root), "assets": [{"path": p.relative_to(assets).as_posix(), "bytes": p.stat().st_size} for p in _files(assets)]}
        if action != "upload" or not asset_path:
            raise CompanionError("project_assets accepts list, or upload with asset_path relative to assets/")
        relative = _relative(asset_path)
        source = _under(assets, relative, exists=True)
        profile = self.http.profile()
        with _project_lock(root):
            data = _read(source, MAX_ASSET)
            local_sha = _sha(data)
            uploaded_name, owned_prefix = _asset_upload_name(root, relative, local_sha)
            # Core media enums list input-root files; subfolder-only uploads can
            # load in the backend while Desktop reports a missing media input.
            subfolder = ""
            boundary = "comfyui-local-" + uuid.uuid4().hex
            fields = []
            for key, value in (("type", "input"), ("subfolder", subfolder), ("overwrite", "false")):
                fields.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode("utf-8"))
            mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
            fields.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{uploaded_name}"\r\nContent-Type: {mime}\r\n\r\n'.encode("utf-8") + data + b"\r\n")
            fields.append(f"--{boundary}--\r\n".encode("ascii"))
            raw = self.http.bytes("POST", "/upload/image", b"".join(fields), content_type=f"multipart/form-data; boundary={boundary}")
            response = _parse_json(raw, "upload response")
            if not isinstance(response, dict) or response.get("type") != "input":
                raise CompanionError("upload mapping returned an unexpected storage type")
            name = _server_relative(response.get("name", ""))
            returned_folder = _server_relative(response.get("subfolder", ""), allow_empty=True)
            if "/" in name or returned_folder != "" or not name.startswith(owned_prefix) or len(name.encode("utf-8")) > 255:
                raise CompanionError("upload mapping did not preserve the project namespace; no mapping recorded")
            if _read(source, MAX_ASSET) != data:
                raise CompanionError("source asset changed during upload; no mapping recorded")
            literal_reference = {"name": response["name"], "subfolder": response.get("subfolder", ""), "type": "input"}
            normalized_reference = {"name": name, "subfolder": returned_folder, "type": "input"}
            mapping = {"local_path": relative, "local_sha256": local_sha, "bytes": len(data), "server_url": self.http.url, "profile": profile, "requested_name": uploaded_name, "name": name, "subfolder": returned_folder, "type": "input", "input_path": name, "server_reference": literal_reference, "normalized_server_reference": normalized_reference, "reference_normalization": _reference_normalization(literal_reference, normalized_reference), "at": _now()}
            lock_path = _under(root, ".comfy/companion-assets.json")
            previous = _read(lock_path) if lock_path.exists() else None
            lock = _parse_json(previous, "asset mapping") if previous is not None else {"schema": "comfyui-local/assets/1", "assets": {}}
            if not isinstance(lock, dict) or lock.get("schema") != "comfyui-local/assets/1" or not isinstance(lock.get("assets"), dict):
                raise CompanionError("existing asset mapping is not a companion-owned map; upload completed but mapping was not overwritten")
            lock["assets"][relative] = mapping
            _managed_replace(lock_path, _json_bytes(lock), previous)
        return mapping

    def record_run(self, project_root: str, prompt_id: str, workflow_path: str | None = None) -> dict:
        root = _project(project_root)
        try:
            if str(uuid.UUID(prompt_id)) != prompt_id.lower():
                raise ValueError()
        except (ValueError, AttributeError) as exc:
            raise CompanionError("prompt_id must be the actual UUID returned by ComfyUI") from exc
        self.http.profile()
        run_root = _under(root, f".comfy/recorded-runs/{prompt_id}")
        record_path = run_root / "record.json"
        if record_path.exists():
            return _parse_json(_read(record_path), "existing run record")
        history = self.http.json("GET", "/history/" + quote(prompt_id, safe=""))
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        native_status = entry.get("status") if isinstance(entry, dict) else None
        messages = (native_status.get("messages") or []) if isinstance(native_status, dict) else []
        terminal_events = [item[0] for item in messages if isinstance(item, list) and len(item) == 2 and item[0] in {"execution_error", "execution_interrupted"}]
        terminal_failure = isinstance(native_status, dict) and (native_status.get("status_str") == "error" or bool(terminal_events))
        # Native ComfyUI error/interrupted history is terminal with completed=False.
        # Detect its terminal status/events before treating an unfinished run as pending.
        if not isinstance(native_status, dict) or (native_status.get("completed") is not True and not terminal_failure):
            return {"prompt_id": prompt_id, "status": "PENDING", "recorded": False, "effect": "read-only observation; no resubmission or cancellation"}
        prompt = entry.get("prompt")
        graph = prompt[2] if isinstance(prompt, list) and len(prompt) > 2 and isinstance(prompt[2], dict) else {}
        if not graph or prompt[1] != prompt_id:
            raise CompanionError("terminal history lacks the submitted graph; evidence cannot be reconstructed")
        workflow = None
        if workflow_path:
            file = _under(root, workflow_path, exists=True)
            raw = _read(file)
            _workflow(_parse_json(raw, "workflow"))
            workflow = {"path": workflow_path, "sha256": _sha(raw), "scope": "project snapshot supplied for provenance; not asserted equal to submitted API graph"}
        cached: set[str] = set()
        observed_cache = False
        for item in messages:
            if isinstance(item, list) and len(item) == 2 and item[0] == "execution_cached" and isinstance(item[1], dict):
                nodes = item[1].get("nodes")
                if not isinstance(nodes, list):
                    raise CompanionError("history cache observation has an invalid shape")
                observed_cache = True
                cached.update(str(n) for n in nodes)
        sampler_ids = [str(key) for key, node in graph.items() if isinstance(node, dict) and node.get("class_type") in _SAMPLERS]
        sampler_execution = "CACHE_STATUS_UNKNOWN" if sampler_ids and not observed_cache else "NOT_CACHED" if any(key not in cached for key in sampler_ids) else "CACHE_ONLY" if sampler_ids else "NOT_EVALUATED"
        status = "COMPLETED_RECORDED" if not terminal_failure and native_status.get("status_str") == "success" else "FAIL"
        with _project_lock(root):
            if run_root.exists():
                raise CompanionError("an incomplete recording already exists for this run; inspect it instead of overwriting or resubmitting")
            run_root.mkdir(parents=True)
            _create(run_root / "history.json", _json_bytes(history))
            outputs = []
            seen = set()

            def collect(value: Any, node_id: str):
                if isinstance(value, dict):
                    if isinstance(value.get("filename"), str):
                        filename = _server_relative(value["filename"])
                        subfolder = _server_relative(value.get("subfolder", ""), allow_empty=True)
                        if "/" in filename:
                            raise CompanionError("server output filename must be a single relative component")
                        if value.get("type", "output") != "output":
                            return
                        key = (filename, subfolder)
                        if key in seen:
                            return
                        seen.add(key)
                        query = urlencode({"filename": filename, "subfolder": subfolder, "type": "output"})
                        node_folder = "node-" + hashlib.sha256(node_id.encode("utf-8")).hexdigest()[:16]
                        target = _under(root, f"outputs/{prompt_id}/{node_folder}/" + (subfolder + "/" if subfolder else "") + filename)
                        result = self.http.download("/view?" + query, target)
                        literal_reference = {"filename": value["filename"], "subfolder": value.get("subfolder", ""), "type": "output"}
                        normalized_reference = {"filename": filename, "subfolder": subfolder, "type": "output"}
                        outputs.append({"node_id": node_id, "server_reference": literal_reference, "normalized_server_reference": normalized_reference, "reference_normalization": _reference_normalization(literal_reference, normalized_reference), **result})
                    for child in value.values():
                        collect(child, node_id)
                elif isinstance(value, list):
                    for child in value:
                        collect(child, node_id)

            for node_id, value in (entry.get("outputs") or {}).items():
                node_id = str(node_id)
                if not node_id or len(node_id) > 512 or any(ord(c) < 32 for c in node_id):
                    raise CompanionError("output node identifier is invalid")
                collect(value, node_id)
            record = {"schema": "comfyui-local/run/1", "recorded_at": _now(), "project_root": str(root), "server_url": self.http.url, "user_id": self.http.user_id, "prompt_id": prompt_id, "status": status, "native_status": {"status_str": native_status.get("status_str"), "completed": native_status.get("completed"), "terminal_events": terminal_events}, "sampler_execution": sampler_execution, "known_sampler_ids": sampler_ids, "cached_node_ids": sorted(cached), "submitted_graph_sha256": _sha(_json_bytes(graph)), "parameters": graph, "workflow_snapshot": workflow, "outputs": outputs, "output_bytes_verified": bool(outputs), "quality_review": "NOT_RUN", "decode_review": "NOT_RUN", "generation_scope": "server history and exact output bytes; completion or tools loaded alone do not prove visual/audio quality or native sampling", "no_resubmission_or_cancellation": True}
            _create(record_path, _json_bytes(record))
        return record
