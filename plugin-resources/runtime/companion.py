"""MIT MCP companion entrypoint. Prepared runtime only; no automatic setup."""

from __future__ import annotations

import sys
from typing import Literal

from mcp.server.mcpserver import MCPServer

from companion_ops import Companion
from config import load_config


mcp = MCPServer(
    "comfyui-local-projects",
    instructions="Manage explicit local ComfyUI projects and complete visual workflows. "
    "Generation belongs to the official ComfyUI MCP. Preserve sources, unsaved canvases, "
    "other users and jobs. Read available schemas before choosing a modality. "
    "Use the comfyui-local skill for creation, review and user guidance.",
)
_operations: Companion | None = None


def _get_operations() -> Companion:
    global _operations
    if _operations is None:
        _operations = Companion(load_config())
    return _operations


@mcp.tool()
def local_status() -> dict:
    """Read the configured loopback server's profile, queue and system stats without launching models or checking updates."""
    return _get_operations().local_status()


@mcp.tool()
def project(action: Literal["list", "create", "status"], project_root: str) -> dict:
    """List a collection's immediate projects, create a new/empty project, or inspect its exact root. project_root is an absolute local path. Use project/1, never reinitialize an ancestor."""
    return _get_operations().project(action, project_root)


@mcp.tool()
def workflow_document(action: Literal["read", "create", "copy"], project_root: str, path: str, document: dict | None = None, source_path: str | None = None) -> dict:
    """Read or create an immutable complete visual workflow, including groups, notes and subgraphs. Paths are relative to the exact project; new files never overwrite. copy uses source_path in the same project."""
    return _get_operations().workflow_document(action, project_root, path, document, source_path)


@mcp.tool()
def workflow_edit(project_root: str, path: str, operations: list[dict], expected_sha256: str, output_path: str | None = None) -> dict:
    """Apply an atomic CLI recipe to a new visual revision. Allowed ops: add_node, connect, set_widget, set_node_field, delete_node. Requires the reviewed source SHA; never runs the graph or alters its source."""
    return _get_operations().workflow_edit(project_root, path, operations, expected_sha256, output_path)


@mcp.tool()
def workflow_store(action: Literal["list", "get", "save", "delete"], project_root: str, name: str | None = None, path: str | None = None, replace: bool = False, expected_sha256: str | None = None) -> dict:
    """Store/open visual workflows in the configured Comfy-User profile for Desktop Workflows. save is create-only. Explicit authorized replace/delete uses replace=true, current SHA and a recoverable backup; no atomic server CAS or live canvas editing is claimed."""
    return _get_operations().workflow_store(action, project_root, name, path, replace, expected_sha256)


@mcp.tool()
def project_assets(action: Literal["list", "upload"], project_root: str, asset_path: str | None = None) -> dict:
    """List project assets or upload one asset-relative file to ComfyUI input without overwrite. Return and preserve the confirmed server filename/subfolder mapping; isolate project namespaces."""
    return _get_operations().project_assets(action, project_root, asset_path)


@mcp.tool()
def record_run(project_root: str, prompt_id: str, workflow_path: str | None = None) -> dict:
    """Observe a real ComfyUI run UUID and record its history, parameters and exact output bytes/SHA. Pending stays pending. No generation, retry or cancel; quality and decode review remain NOT_RUN until inspected separately."""
    return _get_operations().record_run(project_root, prompt_id, workflow_path)


if __name__ == "__main__":
    try:
        _get_operations()  # Fail clearly before advertising tools if setup is missing.
        mcp.run(transport="stdio")
    except (OSError, ValueError) as error:
        print(f"comfyui-local: {error}", file=sys.stderr)
        raise SystemExit(1) from error
