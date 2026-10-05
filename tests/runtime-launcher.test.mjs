import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const ROOT = path.resolve(import.meta.dirname, "..");
const RUNTIME = path.join(ROOT, "plugin-resources", "runtime");
const PINNED = { "comfy-mcp": "0.10.0", "comfy-cli": "1.22.0", mcp: "2.0.0" };

test("both MCP entrypoints use the prepared offline runtime", async () => {
  const manifest = JSON.parse(await readFile(path.join(ROOT, "mcp.json"), "utf8"));
  assert.deepEqual(Object.keys(manifest.mcpServers).sort(), ["comfyui","comfyui-projects"]);
  for (const [name, server] of Object.entries(manifest.mcpServers)) {
    assert.equal(server.type, "stdio");
    assert.equal(server.command, "uv");
    for (const flag of ["--frozen","--no-sync","--offline","--no-python-downloads","--no-env-file"]) assert.ok(server.args.includes(flag), name + " must retain " + flag);
    assert.equal(server.args[server.args.indexOf("python") + 1], "-B");
    assert.equal(server.env.UV_PROJECT_ENVIRONMENT, "${PLUGIN_DATA}/runtime");
    assert.equal(server.args[server.args.indexOf("--python") + 1], "${PLUGIN_DATA}/runtime");
    assert.equal(server.env.PYTHONDONTWRITEBYTECODE, "1");
    assert.equal(server.args.at(-1), name === "comfyui" ? "official" : "companion");
  }
});

test("runtime metadata preserves exact direct pins and hashed locked artifacts", async () => {
  const pyproject = await readFile(path.join(RUNTIME, "pyproject.toml"), "utf8");
  const lock = await readFile(path.join(RUNTIME, "uv.lock"), "utf8");
  for (const [name, version] of Object.entries(PINNED)) {
    assert.match(pyproject, new RegExp('"' + name.replace("-", "\\-") + '==' + version.replaceAll(".", "\\.") + '"'));
    assert.match(lock, new RegExp('name = "' + name.replace("-", "\\-") + '"[\\s\\S]{0,300}?version = "' + version.replaceAll(".", "\\.") + '"'));
  }
  const registryBlocks = lock.split(/\n\[\[package\]\]\n/).filter((block) => /source = \{ registry = /.test(block));
  assert.ok(registryBlocks.length > 0);
  for (const block of registryBlocks) assert.match(block, /hash = "sha256:[a-f0-9]{64}"/);
});

test("an absent prepared runtime is rejected without creating a virtual environment", async (t) => {
  const uv = spawnSync("uv", ["--version"], { encoding: "utf8" });
  if (uv.status !== 0) { t.skip("uv absent; prepared-runtime scenario NOT_RUN"); return; }
  const directory = await mkdtemp(path.join(os.tmpdir(), "comfy-missing-runtime-"));
  t.after(() => rm(directory, { recursive:true, force:true }));
  const server = JSON.parse(await readFile(path.join(ROOT, "mcp.json"), "utf8")).mcpServers.comfyui;
  const expand = (value) => value.replaceAll("${PLUGIN_ROOT}", ROOT).replaceAll("${PLUGIN_DATA}", directory);
  const result = spawnSync(server.command, server.args.map(expand), {
    cwd: ROOT, encoding:"utf8", timeout:30000,
    env:{...process.env,PLUGIN_DATA:directory,...Object.fromEntries(Object.entries(server.env).map(([k,v])=>[k,expand(v)]))}
  });
  assert.notEqual(result.status, 0);
  assert.doesNotMatch(result.stderr ?? "", /Downloading|Creating virtual environment/i);
  await assert.rejects(stat(path.join(directory, "runtime")), { code:"ENOENT" });
});

test("configuration and launcher are fail-closed around local-only runtime inputs", async (t) => {
  const candidates=process.platform==="win32"?["python","python3"]:["python3","python"];
  const python=candidates.find((cmd)=>spawnSync(cmd,["-I","-B","-c","import sys; assert sys.version_info >= (3,10)"],{encoding:"utf8"}).status===0);
  if(!python){t.skip("Python >=3.10 absent; configuration behavior NOT_RUN");return;}
  const code=`
import json, pathlib, sys, tempfile
sys.path.insert(0, ${JSON.stringify(path.join(ROOT,"plugin-resources","runtime"))})
from config import ConfigurationError, normalize_server_url, validate_config
with tempfile.TemporaryDirectory() as td:
    root=pathlib.Path(td); core=root/"core"; core.mkdir()
    (core/"main.py").write_text("#")
    (core/"nodes.py").write_text("#")
    (core/"comfy").mkdir(); (core/"comfy_extras").mkdir()
    data=root/"data"; data.mkdir()
    doc={"schema_version":1,"server_url":"http://127.0.0.1:8188/","workspace":str(core),"user_id":None}
    cfg=validate_config(doc,data)
    assert normalize_server_url("http://127.0.0.1:8188")=="http://127.0.0.1:8188"
    for u in ["https://127.0.0.1:8188","http://example.com:8188","http://0.0.0.0:8188","http://user:secret@127.0.0.1:8188"]:
        try: normalize_server_url(u)
        except ConfigurationError: pass
        else: raise AssertionError(u)
print("PASS")
`;
  const result=spawnSync(python,["-I","-B","-c",code],{encoding:"utf8",timeout:30000,env:{...process.env,PYTHONDONTWRITEBYTECODE:"1"}});
  assert.equal(result.status,0,(result.stdout??"")+"\n"+(result.stderr??""));
});
