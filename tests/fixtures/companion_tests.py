"""Offline stdlib behavioral tests. No installed MCP SDK or GPU is required."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugin-resources" / "runtime"))
from companion_ops import Companion, CompanionError, _no_links


WORKFLOW = {
    "last_node_id": 1,
    "last_link_id": 0,
    "nodes": [{"id": 1, "type": "Source", "pos": [1, 2], "size": [200, 90], "widgets_values": [7], "inputs": [], "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": []}]}],
    "links": [],
    "groups": [{"title": "Keep the group", "bounding": [0, 0, 400, 400]}],
    "definitions": {"subgraphs": [{"id": "fixture-subgraph", "nodes": [], "links": [], "extra": {"note": "Keep the subgraph"}}]},
    "extra": {"notes": [{"text": "Keep this author note"}]},
    "version": 0.4,
}
CATALOG = {
    "Source": {"input": {"required": {"seed": ["INT", {"default": 7, "min": 0, "max": 999999}]}}, "output": ["IMAGE"], "output_name": ["IMAGE"], "name": "Source", "display_name": "Source", "output_node": False, "category": "fixture"},
    "Sink": {"input": {"required": {"image": ["IMAGE"], "label": ["STRING", {"default": "fixture"}]}}, "output": [], "output_name": [], "name": "Sink", "display_name": "Sink", "output_node": True, "category": "fixture"},
}


class FakeComfy:
    def __init__(self):
        self.requests = []
        self.multi_user = False
        self.users = {"default": "Default", "alice": "Alice", "bob": "Bob"}
        self.storage = {}
        self.histories = {}
        self.outputs = {}
        self.force_upload_name = None
        self.force_upload_suffix = None
        self.force_upload_type = None
        self.force_upload_folder = None
        self.windows_upload_subfolders = False
        self.read_count = 0
        self.change_on_read = None
        state = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send_data(self, status, value=None, *, raw=None):
                data = raw if raw is not None else json.dumps(value).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json" if raw is None else "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def process(self):
                parsed = urlsplit(self.path)
                route = unquote(parsed.path)
                query = parse_qs(parsed.query)
                user = self.headers.get("Comfy-User")
                state.requests.append({"method": self.command, "route": route, "query": query, "user": user})
                if route == "/users":
                    return self.send_data(200, {"storage": "server", **({"users": state.users} if state.multi_user else {"migrated": True})})
                if route == "/system_stats":
                    return self.send_data(200, {"devices": [{"type": "fixture", "vram_total": 0}]})
                if route == "/queue":
                    return self.send_data(200, {"queue_running": [], "queue_pending": []})
                if route == "/object_info":
                    return self.send_data(200, CATALOG)
                if route == "/userdata":
                    if query.get("dir") != ["workflows"]:
                        return self.send_data(400, {})
                    files = [{"path": name[len("workflows/"):], "size": len(value), "modified": 0, "created": 0} for (owner, name), value in state.storage.items() if owner == user]
                    return self.send_data(200, files)
                if route.startswith("/userdata/"):
                    name = route[len("/userdata/"):]
                    key = (user, name)
                    if self.command == "GET":
                        state.read_count += 1
                        if state.change_on_read == state.read_count:
                            state.storage[key] = b'{"nodes":[],"changed":true}'
                        if key not in state.storage:
                            return self.send_data(404, {})
                        return self.send_data(200, raw=state.storage[key])
                    if self.command == "POST":
                        if key in state.storage and query.get("overwrite") == ["false"]:
                            return self.send_data(409, {})
                        state.storage[key] = self.rfile.read(int(self.headers["Content-Length"]))
                        return self.send_data(200, {"path": name})
                    if self.command == "DELETE":
                        if key not in state.storage:
                            return self.send_data(404, {})
                        del state.storage[key]
                        return self.send_data(204, raw=b"")
                if route == "/upload/image" and self.command == "POST":
                    body = self.rfile.read(int(self.headers["Content-Length"]))
                    message = BytesParser(policy=policy.default).parsebytes(("Content-Type: " + self.headers["Content-Type"] + "\r\nMIME-Version: 1.0\r\n\r\n").encode("ascii") + body)
                    fields = {}
                    filename = None
                    for part in message.iter_parts():
                        name = part.get_param("name", header="content-disposition")
                        if name == "image":
                            filename = part.get_filename()
                            fields["data"] = part.get_payload(decode=True)
                        else:
                            fields[name] = part.get_payload(decode=True).decode("utf-8")
                    state.last_upload = fields
                    state.last_upload["filename"] = filename
                    folder = state.force_upload_folder if state.force_upload_folder is not None else fields["subfolder"].replace("/", "\\") if state.windows_upload_subfolders else fields["subfolder"]
                    returned_name = state.force_upload_name or (Path(filename).stem + state.force_upload_suffix + Path(filename).suffix if state.force_upload_suffix else filename)
                    return self.send_data(200, {"name": returned_name, "subfolder": folder, "type": state.force_upload_type or "input"})
                if route.startswith("/history/"):
                    prompt_id = route[len("/history/"):]
                    return self.send_data(200, {prompt_id: state.histories[prompt_id]} if prompt_id in state.histories else {})
                if route == "/view":
                    key = (query.get("filename", [""])[0], query.get("subfolder", [""])[0], query.get("type", [""])[0])
                    if key not in state.outputs:
                        return self.send_data(404, {})
                    return self.send_data(200, raw=state.outputs[key])
                return self.send_data(404, {})

            do_GET = do_POST = do_DELETE = process

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class CompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = FakeComfy()

    @classmethod
    def tearDownClass(cls):
        cls.server.close()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="comfy-companion-", dir=os.environ.get("TEMP"))
        self.addCleanup(self.temporary.cleanup)
        self.collection = Path(self.temporary.name)
        self.server.requests.clear()
        self.server.storage.clear()
        self.server.histories.clear()
        self.server.outputs.clear()
        self.server.multi_user = False
        self.server.force_upload_name = None
        self.server.force_upload_suffix = None
        self.server.force_upload_type = None
        self.server.force_upload_folder = None
        self.server.windows_upload_subfolders = False
        self.server.read_count = 0
        self.server.change_on_read = None
        self.config = {"server_url": self.server.url, "user_id": None, "workspace": self.collection, "data_dir": self.collection / "private", "comfy_bin": Path(sys.executable)}
        self.operations = Companion(self.config)
        self.first = self.collection / "first"
        self.second = self.collection / "second"
        self.operations.project("create", str(self.first))
        self.operations.project("create", str(self.second))

    def visual(self, root=None, document=None):
        return self.operations.workflow_document("create", str(root or self.first), "blueprints/workflows/source.json", document or WORKFLOW)

    def test_project_collection_and_exact_roots_remain_separate(self):
        projects = self.operations.project("list", str(self.collection))["projects"]
        self.assertEqual({p["project_root"] for p in projects}, {str(self.first), str(self.second)})
        self.visual(self.first)
        self.assertEqual(self.operations.project("status", str(self.second))["workflows"], [])
        with self.assertRaises(CompanionError):
            self.operations.project("create", str(self.first / "nested"))
        with self.assertRaises(CompanionError):
            self.operations.project("status", str(self.first / "assets"))
        self.assertFalse((self.first / "nested").exists())

    def test_visual_read_copy_preserves_complete_document_and_refuses_collision(self):
        result = self.visual()
        document = self.operations.workflow_document("read", str(self.first), "blueprints/workflows/source.json")
        self.assertEqual(document["document"], WORKFLOW)
        copied = self.operations.workflow_document("copy", str(self.first), "blueprints/workflows/copy.json", source_path="blueprints/workflows/source.json")
        self.assertEqual(result["sha256"], copied["sha256"])
        with self.assertRaises(CompanionError):
            self.visual()
        self.assertEqual(document, self.operations.workflow_document("read", str(self.first), "blueprints/workflows/source.json"))

    def test_paths_encoded_traversal_reparse_and_nonvisual_prompts_are_refused(self):
        for value in ("../escape.json", "/absolute.json", "blueprints/../escape.json", "blueprints/%2e%2e/a.json", "C:/escape.json", "blueprints/CON.json", "blueprints/a\\b.json"):
            with self.subTest(path=value), self.assertRaises(CompanionError):
                self.operations.workflow_document("create", str(self.first), value, WORKFLOW)
        with self.assertRaises(CompanionError):
            self.visual(document={"1": {"class_type": "KSampler", "inputs": {}}})
        path = self.first / "assets" / "fake-reparse"
        path.mkdir()
        actual = Path.lstat
        def reparse(item):
            if item == path:
                class Info:
                    st_mode = 0o40755
                    st_file_attributes = 0x400
                return Info()
            return actual(item)
        with patch.object(Path, "lstat", reparse), self.assertRaises(CompanionError):
            _no_links(path / "child.json")

    def test_local_status_only_reads_profile_stats_queue(self):
        result = self.operations.local_status()
        self.assertEqual(result["model_execution"], "NOT_RUN")
        self.assertEqual([r["route"] for r in self.server.requests], ["/users", "/system_stats", "/queue"])
        self.assertTrue(all(r["method"] == "GET" for r in self.server.requests))

    def test_endpoint_requires_http_loopback_and_explicit_valid_port(self):
        for url in ("https://127.0.0.1:8188", "http://127.0.0.1", "http://localhost/", "http://[::1]", "http://localhost:0", "http://127.0.0.1:65536", "http://127.0.0.1:invalid"):
            with self.subTest(url=url), self.assertRaises(CompanionError):
                Companion({**self.config, "server_url": url})
        self.assertEqual(self.server.requests, [])
        self.assertEqual(Companion(self.config).http.url, self.server.url)

    def test_workflow_store_create_only_and_headers_are_profile_specific(self):
        self.server.multi_user = True
        alice = Companion({**self.config, "user_id": "alice"})
        bob = Companion({**self.config, "user_id": "bob"})
        self.visual()
        self.visual(self.second, {**WORKFLOW, "extra": {"owner": "second"}})
        alice.workflow_store("save", str(self.first), "project/demo.json", "blueprints/workflows/source.json")
        bob.workflow_store("save", str(self.second), "project/demo.json", "blueprints/workflows/source.json")
        self.assertNotEqual(self.server.storage[("alice", "workflows/project/demo.json")], self.server.storage[("bob", "workflows/project/demo.json")])
        posts = [r for r in self.server.requests if r["method"] == "POST"]
        self.assertEqual([r["user"] for r in posts], ["alice", "bob"])
        self.assertTrue(all(r["query"]["overwrite"] == ["false"] for r in posts))
        with self.assertRaises(CompanionError):
            alice.workflow_store("save", str(self.first), "project/demo.json", "blueprints/workflows/source.json")

    def test_unknown_profile_never_falls_back_to_default(self):
        self.visual()
        unknown = Companion({**self.config, "user_id": "unknown"})
        with self.assertRaises(CompanionError):
            unknown.workflow_store("save", str(self.first), "demo.json", "blueprints/workflows/source.json")
        self.assertEqual(self.server.storage, {})
        self.server.multi_user = True
        with self.assertRaises(CompanionError):
            unknown.workflow_store("list", str(self.first))
        self.assertEqual(self.server.storage, {})

    def test_replace_delete_require_hash_and_preserve_backup(self):
        self.visual()
        saved = self.operations.workflow_store("save", str(self.first), "demo.json", "blueprints/workflows/source.json")
        original = self.server.storage[("default", "workflows/demo.json")]
        changed = {**WORKFLOW, "extra": {"changed": True}}
        self.operations.workflow_document("create", str(self.first), "blueprints/workflows/new.json", changed)
        with self.assertRaises(CompanionError):
            self.operations.workflow_store("save", str(self.first), "demo.json", "blueprints/workflows/new.json", True, "0" * 64)
        self.assertEqual(self.server.storage[("default", "workflows/demo.json")], original)
        replaced = self.operations.workflow_store("save", str(self.first), "demo.json", "blueprints/workflows/new.json", True, saved["sha256"])
        self.assertEqual(Path(replaced["backup_path"]).read_bytes(), original)
        with self.assertRaises(CompanionError):
            self.operations.workflow_store("delete", str(self.first), "demo.json", expected_sha256=replaced["sha256"])
        deleted = self.operations.workflow_store("delete", str(self.first), "demo.json", replace=True, expected_sha256=replaced["sha256"])
        self.assertTrue(deleted["deleted"])
        self.assertEqual(hashlib.sha256(Path(deleted["backup_path"]).read_bytes()).hexdigest(), replaced["sha256"])

    def test_change_between_backup_and_mutation_refuses_update(self):
        self.visual()
        saved = self.operations.workflow_store("save", str(self.first), "demo.json", "blueprints/workflows/source.json")
        self.server.read_count = 0
        self.server.change_on_read = 2
        before_posts = len([r for r in self.server.requests if r["method"] == "POST"])
        with self.assertRaises(CompanionError):
            self.operations.workflow_store("save", str(self.first), "demo.json", "blueprints/workflows/source.json", True, saved["sha256"])
        self.assertEqual(len([r for r in self.server.requests if r["method"] == "POST"]), before_posts)
        self.assertEqual(len(list((self.first / ".comfy" / "backups").glob("*.json"))), 1)

    def test_cli_edits_new_revision_with_explicit_environment_and_preserves_source(self):
        source = self.visual()
        original = Path(source["path"]).read_bytes()
        updated = copy.deepcopy(WORKFLOW)
        updated["nodes"][0]["widgets_values"] = [99]
        def stub(command, **kwargs):
            self.assertFalse(kwargs["shell"])
            self.assertEqual(kwargs["cwd"], self.first)
            self.assertEqual(kwargs["env"]["COMFY_WHERE"], "local")
            self.assertEqual(kwargs["env"]["COMFY_PROJECT"], str(self.first))
            self.assertNotIn("COMFY_CLOUD_URL", kwargs["env"])
            self.assertIn("--stdout", command)
            self.assertIn("--input", command)
            self.assertEqual(command[command.index("--ack") + 1], "full")
            self.assertEqual(json.loads(kwargs["input"]), [{"op": "set_widget", "node": "1", "widget": "seed", "value": 99}])
            return subprocess.CompletedProcess(command, 0, json.dumps({"ok": True, "data": {"count": 1, "ops": [{"op": "set_widget", "node_id": 1, "widget": "seed", "value": 99}], "workflow_json": updated}}), "")
        with patch.dict(os.environ, {"COMFY_CLOUD_URL": "https://example.invalid", "COMFY_WHERE": "cloud"}), patch("companion_ops.subprocess.run", side_effect=stub):
            result = self.operations.workflow_edit(str(self.first), "blueprints/workflows/source.json", [{"op": "set_widget", "node": "1", "widget": "seed", "value": 99}], source["sha256"])
        self.assertEqual(Path(source["path"]).read_bytes(), original)
        self.assertEqual(json.loads(Path(result["path"]).read_bytes()), updated)
        self.assertEqual(list((self.first / ".comfy").glob("edit-*")), [])

    def test_invalid_batch_stale_hash_and_cli_timeout_preserve_source(self):
        source = self.visual()
        original = Path(source["path"]).read_bytes()
        with self.assertRaises(CompanionError):
            self.operations.workflow_edit(str(self.first), "blueprints/workflows/source.json", [{"op": "clear"}], source["sha256"])
        with self.assertRaises(CompanionError):
            self.operations.workflow_edit(str(self.first), "blueprints/workflows/source.json", [{"op": "delete_node", "node": "1"}], "0" * 64)
        response = subprocess.CompletedProcess([], 1, json.dumps({"ok": False, "error": {"code": "workflow_edit_invalid"}}), "")
        with patch("companion_ops.subprocess.run", return_value=response), self.assertRaises(CompanionError):
            self.operations.workflow_edit(str(self.first), "blueprints/workflows/source.json", [{"op": "delete_node", "node": "missing"}], source["sha256"])
        with patch("companion_ops.subprocess.run", side_effect=subprocess.TimeoutExpired([], 90)), self.assertRaises(CompanionError):
            self.operations.workflow_edit(str(self.first), "blueprints/workflows/source.json", [{"op": "delete_node", "node": "1"}], source["sha256"])
        self.assertEqual(Path(source["path"]).read_bytes(), original)
        self.assertEqual(len(list((self.first / "blueprints" / "workflows").glob("*.json"))), 1)

    def test_named_widgets_use_effective_receipt_target_and_canonical_value(self):
        document = copy.deepcopy(WORKFLOW)
        document["nodes"][0]["widgets_values"] = [7, "randomize"]
        document["nodes"][0]["widgets_values_named"] = {"seed": 7, "control_after_generate": "randomize", "editor_metadata": "retain"}
        second = copy.deepcopy(document["nodes"][0])
        second["id"] = 2
        document["nodes"].append(second)
        source = self.visual(document=document)
        before = Path(source["path"]).read_bytes()
        updated = copy.deepcopy(document)
        updated["nodes"][1]["widgets_values"][0] = 99
        normalization = {"code": "normalized_value", "message": "fixture canonical value from CLI"}
        receipt = {"count": 1, "base_version": 0, "ops": [{"op": "set_widget", "node_id": 2, "widget": "seed", "value": 99, "redirected_from": "1.seed", "warnings": [normalization]}], "workflow_json": updated}
        with patch("companion_ops.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps({"ok": True, "data": receipt}), "")):
            edited = self.operations.workflow_edit(str(self.first), "blueprints/workflows/source.json", [{"op": "set_widget", "node": "1", "widget": "seed", "value": 100}], source["sha256"])
        actual = json.loads(Path(edited["path"]).read_bytes())
        self.assertEqual(actual["nodes"][0], document["nodes"][0])
        self.assertEqual(actual["nodes"][1]["widgets_values_named"], {"seed": 99, "control_after_generate": "randomize", "editor_metadata": "retain"})
        self.assertEqual(actual["nodes"][1]["widgets_values"], [99, "randomize"])
        self.assertEqual(Path(source["path"]).read_bytes(), before)
        self.assertNotIn("ops", edited["cli_receipt"])
        self.assertEqual(edited["cli_receipt"]["named_widgets_reconciled"], [{"node_path": ["2"], "widgets": ["seed"]}])
        self.assertEqual(edited["cli_receipt"]["widget_writes"], [{"node_path": ["2"], "widget": "seed", "value": 99}])
        self.assertEqual(edited["cli_receipt"]["warnings"], [normalization])
        self.assertEqual(edited["cli_receipt"]["base_version"], 0)
        self.assertNotIn("version", edited["cli_receipt"])
        self.assertNotIn("changed", edited["cli_receipt"])

    def test_cli_unsupported_dynamic_noop_rejects_entire_revision_and_preserves_source(self):
        source = self.visual()
        before = Path(source["path"]).read_bytes()
        receipt = {"count": 1, "ops": [{"op": "set_widget", "node_id": 1, "widget": "format.inactive", "value": 99, "warnings": [{"code": "unknown_dynamic_sub_input", "message": "nothing was written"}]}], "workflow_json": WORKFLOW}
        with patch("companion_ops.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps({"ok": True, "data": receipt}), "")), self.assertRaisesRegex(CompanionError, "unsupported dynamic sub-input"):
            self.operations.workflow_edit(str(self.first), "blueprints/workflows/source.json", [{"op": "set_widget", "node": "1", "widget": "format.inactive", "value": 99}], source["sha256"])
        self.assertEqual(Path(source["path"]).read_bytes(), before)
        self.assertEqual(len(list((self.first / "blueprints" / "workflows").glob("*.json"))), 1)
        self.assertEqual(list((self.first / ".comfy").glob("edit-*")), [])

    def test_repeated_effective_widget_receipt_rejects_first_winner_revision(self):
        document = copy.deepcopy(WORKFLOW)
        document["nodes"][0]["widgets_values"] = [7, "randomize"]
        document["nodes"][0]["widgets_values_named"] = {"seed": 7, "control_after_generate": "randomize", "editor_metadata": "retain"}
        source = self.visual(document=document)
        before = Path(source["path"]).read_bytes()
        first_wins = copy.deepcopy(document)
        first_wins["nodes"][0]["widgets_values"][0] = 19
        receipt = {"count": 2, "aliases": {"same_control": 1}, "ops": [{"op": "set_widget", "node_id": 1, "widget": "seed", "value": 19}, {"op": "set_widget", "node_id": 999, "widget": "seed", "value": 23, "promoted": {"instance_path": ["1"], "value_index": 0, "host_widgets_values": [19, "randomize"]}}], "workflow_json": first_wins}
        recipe = [{"op": "set_widget", "node": "1", "widget": "seed", "value": 19}, {"op": "set_widget", "node": "$same_control", "widget": "seed", "value": 23}]
        with patch("companion_ops.subprocess.run", return_value=subprocess.CompletedProcess([], 0, json.dumps({"ok": True, "data": receipt}), "")), self.assertRaisesRegex(CompanionError, "one write per control"):
            self.operations.workflow_edit(str(self.first), "blueprints/workflows/source.json", recipe, source["sha256"])
        self.assertEqual(Path(source["path"]).read_bytes(), before)
        self.assertEqual(len(list((self.first / "blueprints" / "workflows").glob("*.json"))), 1)
        self.assertEqual(list((self.first / ".comfy").glob("edit-*")), [])
        self.assertEqual(first_wins["nodes"][0]["widgets_values_named"], document["nodes"][0]["widgets_values_named"])

    def test_source_change_during_cli_prevents_revision_write(self):
        source = self.visual()
        def stub(command, **kwargs):
            Path(source["path"]).write_text(json.dumps({"nodes": [], "external": True}), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, json.dumps({"ok": True, "data": {"count": 1, "ops": [{"op": "delete_node", "node_id": 1}], "workflow_json": WORKFLOW}}), "")
        with patch("companion_ops.subprocess.run", side_effect=stub), self.assertRaises(CompanionError):
            self.operations.workflow_edit(str(self.first), "blueprints/workflows/source.json", [{"op": "delete_node", "node": "1"}], source["sha256"])
        self.assertEqual(len(list((self.first / "blueprints" / "workflows").glob("*.json"))), 1)

    def test_upload_preserves_confirmed_filename_mapping_and_project_namespace(self):
        for root in (self.first, self.second):
            (root / "assets" / "nested").mkdir()
            (root / "assets" / "nested" / "image.png").write_bytes(b"private fixture bytes")
        self.server.force_upload_suffix = " (1)"
        one = self.operations.project_assets("upload", str(self.first), "nested/image.png")
        two = self.operations.project_assets("upload", str(self.second), "nested/image.png")
        self.assertNotEqual(one["name"], two["name"])
        self.assertEqual(one["subfolder"], "")
        self.assertEqual(two["subfolder"], "")
        self.assertTrue(one["name"].startswith("comfyui-local-"))
        self.assertTrue(one["name"].endswith("-image (1).png"))
        self.assertEqual(one["input_path"], one["name"])
        self.assertEqual(self.server.last_upload["overwrite"], "false")
        mapping = json.loads((self.first / ".comfy" / "companion-assets.json").read_bytes())
        self.assertEqual(mapping["assets"]["nested/image.png"]["name"], one["name"])
        self.assertEqual(mapping["assets"]["nested/image.png"]["local_path"], "nested/image.png")
        self.assertEqual(one["requested_name"].replace(".png", " (1).png"), one["name"])
        self.assertTrue((self.first / "assets" / "nested" / "image.png").is_file())

    def test_upload_root_response_preserves_provenance_and_user_path_guards(self):
        (self.first / "assets" / "nested").mkdir()
        (self.first / "assets" / "nested" / "image.png").write_bytes(b"fixture input bytes")
        self.server.windows_upload_subfolders = True
        result = self.operations.project_assets("upload", str(self.first), "nested/image.png")
        literal = result["server_reference"]["subfolder"]
        self.assertEqual(literal, "")
        self.assertEqual(result["subfolder"], "")
        self.assertEqual(result["input_path"], result["name"])
        self.assertEqual(result["normalized_server_reference"]["subfolder"], result["subfolder"])
        self.assertEqual(result["reference_normalization"]["subfolder"], "unchanged")
        self.assertEqual(result["reference_normalization"]["name"], "unchanged")
        stored = json.loads((self.first / ".comfy" / "companion-assets.json").read_bytes())
        self.assertEqual(stored["assets"]["nested/image.png"]["server_reference"]["subfolder"], literal)
        with self.assertRaises(CompanionError):
            self.operations.project_assets("upload", str(self.first), "nested\\image.png")

    def test_upload_windows_adversarial_server_references_are_rejected_without_mapping(self):
        (self.first / "assets" / "image.png").write_bytes(b"fixture input bytes")
        for folder in ("\\\\server\\share", "C:\\outside", "..\\escape", "safe\\..\\escape", "safe\\%2e%2e", "safe\\control\n", "/absolute"):
            with self.subTest(folder=folder), self.assertRaises(CompanionError):
                self.server.force_upload_folder = folder
                self.operations.project_assets("upload", str(self.first), "image.png")
        self.server.force_upload_folder = None
        for filename in ("..\\escaped.png", "C:\\escaped.png", "nested\\image.png", "%2e%2e.png"):
            with self.subTest(filename=filename), self.assertRaises(CompanionError):
                self.server.force_upload_name = filename
                self.operations.project_assets("upload", str(self.first), "image.png")
        self.server.force_upload_name = "foreign-prefix-image.png"
        with self.assertRaises(CompanionError):
            self.operations.project_assets("upload", str(self.first), "image.png")
        self.server.force_upload_name = None
        self.server.force_upload_type = "output"
        with self.assertRaises(CompanionError):
            self.operations.project_assets("upload", str(self.first), "image.png")
        self.assertFalse((self.first / ".comfy" / "companion-assets.json").exists())
        self.assertEqual((self.first / "assets" / "image.png").read_bytes(), b"fixture input bytes")

    def test_root_asset_names_bind_relative_path_content_and_profile_with_portable_length(self):
        self.server.multi_user = True
        alice = Companion({**self.config, "user_id": "alice"})
        bob = Companion({**self.config, "user_id": "bob"})
        for folder in ("one", "two"):
            (self.first / "assets" / folder).mkdir()
            (self.first / "assets" / folder / "image.png").write_bytes(b"same bytes")
        first = alice.project_assets("upload", str(self.first), "one/image.png")
        different_path = alice.project_assets("upload", str(self.first), "two/image.png")
        self.assertNotEqual(first["name"], different_path["name"])
        (self.first / "assets" / "one" / "image.png").write_bytes(b"changed bytes")
        changed = alice.project_assets("upload", str(self.first), "one/image.png")
        self.assertNotEqual(first["name"], changed["name"])
        long_basename = "á" * 70 + ".png"
        (self.second / "assets" / long_basename).write_bytes(b"unicode filename")
        portable = bob.project_assets("upload", str(self.second), long_basename)
        self.assertLessEqual(len(portable["requested_name"].encode("utf-8")), 200)
        self.assertLessEqual(len(portable["name"].encode("utf-16-le")) // 2, 200)
        self.assertTrue(portable["name"].endswith(".png"))
        self.assertEqual(portable["local_path"], long_basename)
        self.assertEqual(portable["profile"]["user_id"], "bob")
        self.assertTrue(all(request["user"] in {"alice", "bob"} for request in self.server.requests))
        self.assertTrue(all(result["subfolder"] == "" for result in (first, different_path, changed, portable)))
        self.assertEqual(self.server.last_upload["overwrite"], "false")

    def test_pending_run_only_observes_and_never_posts_or_cancels(self):
        prompt_id = str(uuid.uuid4())
        self.server.histories[prompt_id] = {"prompt": [1, prompt_id, {"9:4": {"class_type": "KSampler", "inputs": {"seed": 123}}}, {}], "status": {"completed": False, "status_str": "running", "messages": [["execution_start", {"prompt_id": prompt_id}]]}, "outputs": {}}
        for _ in range(2):
            result = self.operations.record_run(str(self.first), prompt_id)
            self.assertEqual(result["status"], "PENDING")
        self.assertTrue(all(r["method"] == "GET" for r in self.server.requests))
        self.assertFalse((self.first / ".comfy" / "recorded-runs").exists())

    def test_history_transport_timeout_is_not_retried_or_cancelled(self):
        prompt_id = str(uuid.uuid4())
        actual_open = self.operations.http.opener.open
        attempted = []
        def timeout_history(request, *args, **kwargs):
            if "/history/" in request.full_url:
                attempted.append(request)
                raise TimeoutError("fixture history timeout")
            return actual_open(request, *args, **kwargs)
        with patch.object(self.operations.http.opener, "open", side_effect=timeout_history), self.assertRaises(CompanionError):
            self.operations.record_run(str(self.first), prompt_id)
        self.assertEqual(len(attempted), 1)
        self.assertTrue(all(r["method"] == "GET" for r in self.server.requests))
        self.assertFalse((self.first / ".comfy" / "recorded-runs").exists())

    def successful_history(self, prompt_id, *, cached=False, filename="result.png"):
        self.server.histories[prompt_id] = {"prompt": [1, prompt_id, {"9:4": {"class_type": "KSampler", "inputs": {"seed": 123}}, "9:7": {"class_type": "SaveImage", "inputs": {}}}, {}], "status": {"completed": True, "status_str": "success", "messages": [["execution_start", {"prompt_id": prompt_id}], ["execution_cached", {"nodes": ["9:4"] if cached else []}], ["execution_success", {"prompt_id": prompt_id}]]}, "outputs": {"9:7": {"images": [{"filename": filename, "subfolder": "videos", "type": "output"}]}}}
        self.server.outputs[(filename, "videos", "output")] = b"actual output bytes, not a claimed PASS"

    def test_terminal_error_completed_false_records_failure_history_and_partial_outputs(self):
        prompt_id = str(uuid.uuid4())
        self.successful_history(prompt_id)
        entry = self.server.histories[prompt_id]
        entry["status"] = {"completed": False, "status_str": "error", "messages": [["execution_start", {"prompt_id": prompt_id}], ["execution_error", {"prompt_id": prompt_id, "node_id": "9:4", "node_type": "KSampler", "exception_type": "RuntimeError", "exception_message": "fixture failure"}]]}
        result = self.operations.record_run(str(self.first), prompt_id)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["native_status"], {"completed": False, "status_str": "error", "terminal_events": ["execution_error"]})
        stored = json.loads((self.first / ".comfy" / "recorded-runs" / prompt_id / "history.json").read_bytes())
        self.assertEqual(stored[prompt_id], entry)
        self.assertEqual(result["parameters"], entry["prompt"][2])
        self.assertTrue(result["output_bytes_verified"])
        output = result["outputs"][0]
        self.assertEqual(output["sha256"], hashlib.sha256(Path(output["path"]).read_bytes()).hexdigest())
        self.assertEqual(result["quality_review"], "NOT_RUN")
        self.assertTrue(all(r["method"] == "GET" for r in self.server.requests))

    def test_terminal_interrupted_completed_false_records_failure_without_resubmission(self):
        for status_str in ("error", "running"):
            with self.subTest(status_str=status_str):
                prompt_id = str(uuid.uuid4())
                self.successful_history(prompt_id)
                entry = self.server.histories[prompt_id]
                entry["status"] = {"completed": False, "status_str": status_str, "messages": [["execution_start", {"prompt_id": prompt_id}], ["execution_interrupted", {"prompt_id": prompt_id, "node_id": "9:4", "node_type": "KSampler"}]]}
                entry["outputs"] = {}
                result = self.operations.record_run(str(self.first), prompt_id)
                self.assertEqual(result["status"], "FAIL")
                self.assertEqual(result["native_status"]["terminal_events"], ["execution_interrupted"])
                self.assertFalse(result["output_bytes_verified"])
                self.assertEqual(result["outputs"], [])
                self.assertEqual(json.loads((self.first / ".comfy" / "recorded-runs" / prompt_id / "history.json").read_bytes())[prompt_id], entry)
                self.assertTrue((self.first / ".comfy" / "recorded-runs" / prompt_id / "record.json").is_file())
        self.assertTrue(all(r["method"] == "GET" for r in self.server.requests))

    def test_completed_run_records_actual_bytes_without_claiming_quality(self):
        prompt_id = str(uuid.uuid4())
        self.successful_history(prompt_id)
        result = self.operations.record_run(str(self.first), prompt_id)
        self.assertEqual(result["status"], "COMPLETED_RECORDED")
        self.assertEqual(result["sampler_execution"], "NOT_CACHED")
        self.assertEqual(result["quality_review"], "NOT_RUN")
        self.assertEqual(result["decode_review"], "NOT_RUN")
        output = result["outputs"][0]
        self.assertEqual(output["sha256"], hashlib.sha256(Path(output["path"]).read_bytes()).hexdigest())
        request_count = len(self.server.requests)
        again = self.operations.record_run(str(self.first), prompt_id)
        self.assertEqual(result, again)
        self.assertEqual(len(self.server.requests), request_count + 1)  # profile read, no generation or refetch
        self.assertTrue(all(r["method"] == "GET" for r in self.server.requests))

    def test_windows_history_subfolder_downloads_real_normalized_route_and_preserves_literal(self):
        prompt_id = str(uuid.uuid4())
        self.successful_history(prompt_id)
        literal = "fixture_media\\Final"
        reference = self.server.histories[prompt_id]["outputs"]["9:7"]["images"][0]
        reference["subfolder"] = literal
        output_bytes = b"Windows backend fixture output bytes"
        self.server.outputs[("result.png", "fixture_media/Final", "output")] = output_bytes
        result = self.operations.record_run(str(self.first), prompt_id)
        self.assertEqual(result["status"], "COMPLETED_RECORDED")
        output = result["outputs"][0]
        self.assertEqual(Path(output["path"]).read_bytes(), output_bytes)
        self.assertEqual(output["sha256"], hashlib.sha256(output_bytes).hexdigest())
        self.assertEqual(output["server_reference"]["subfolder"], literal)
        self.assertEqual(output["normalized_server_reference"]["subfolder"], "fixture_media/Final")
        self.assertEqual(output["reference_normalization"], {"filename": "unchanged", "subfolder": "windows_separators_to_forward_slashes"})
        request = next(request for request in self.server.requests if request["route"] == "/view")
        self.assertEqual(request["query"]["subfolder"], ["fixture_media/Final"])
        self.assertEqual(request["query"]["filename"], ["result.png"])
        self.assertEqual(result["decode_review"], "NOT_RUN")

    def test_windows_adversarial_history_references_do_not_reach_view(self):
        for folder in ("\\\\server\\share", "C:\\outside", "..\\escape", "safe\\..\\escape", "safe\\%2e%2e", "safe\\control\0", "\\absolute"):
            with self.subTest(folder=folder):
                prompt_id = str(uuid.uuid4())
                self.successful_history(prompt_id)
                self.server.histories[prompt_id]["outputs"]["9:7"]["images"][0]["subfolder"] = folder
                with self.assertRaises(CompanionError):
                    self.operations.record_run(str(self.first), prompt_id)
                self.assertFalse((self.first / ".comfy" / "recorded-runs" / prompt_id / "record.json").exists())
        for filename in ("..\\escaped.png", "C:\\escaped.png", "nested\\image.png", "\\\\server\\share\\image.png", "percent%2f.png"):
            with self.subTest(filename=filename):
                prompt_id = str(uuid.uuid4())
                self.successful_history(prompt_id, filename=filename)
                with self.assertRaises(CompanionError):
                    self.operations.record_run(str(self.first), prompt_id)
        self.assertTrue(all(request["route"] != "/view" for request in self.server.requests))

    def test_cached_history_remains_cached_and_output_traversal_is_rejected(self):
        prompt_id = str(uuid.uuid4())
        self.successful_history(prompt_id, cached=True)
        self.assertEqual(self.operations.record_run(str(self.first), prompt_id)["sampler_execution"], "CACHE_ONLY")
        bad_id = str(uuid.uuid4())
        self.successful_history(bad_id, filename="../escaped.png")
        with self.assertRaises(CompanionError):
            self.operations.record_run(str(self.first), bad_id)
        self.assertFalse((self.collection / "escaped.png").exists())
        self.assertFalse((self.first / ".comfy" / "recorded-runs" / bad_id / "record.json").exists())

    def test_missing_cache_observation_is_unknown_and_mismatched_history_id_is_rejected(self):
        prompt_id = str(uuid.uuid4())
        self.successful_history(prompt_id)
        self.server.histories[prompt_id]["status"]["messages"] = []
        self.assertEqual(self.operations.record_run(str(self.first), prompt_id)["sampler_execution"], "CACHE_STATUS_UNKNOWN")
        other = str(uuid.uuid4())
        self.successful_history(other)
        self.server.histories[other]["prompt"][1] = prompt_id
        with self.assertRaises(CompanionError):
            self.operations.record_run(str(self.first), other)
        self.assertFalse((self.first / ".comfy" / "recorded-runs" / other).exists())

    def test_preexisting_project_lock_is_preserved(self):
        lock = self.first / ".comfy" / "companion.lock"
        lock.write_bytes(b"existing foreign lock")
        with self.assertRaises(CompanionError):
            self.visual()
        self.assertEqual(lock.read_bytes(), b"existing foreign lock")


if __name__ == "__main__":
    unittest.main()
