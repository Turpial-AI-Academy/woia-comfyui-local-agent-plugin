import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const RUNTIME = path.join(ROOT, "plugin-resources", "runtime");
const PINNED = { "comfy-mcp": "0.10.0", "comfy-cli": "1.22.0", mcp: "2.0.0" };

test("both MCP entrypoints use the prepared offline runtime", async () => {
  const manifest = JSON.parse(await readFile(path.join(ROOT, "mcp.json"), "utf8"));
  assert.deepEqual(Object.keys(manifest.mcpServers).sort(), ["comfyui", "comfyui-projects"]);
  for (const [name, server] of Object.entries(manifest.mcpServers)) {
    assert.equal(server.type, "stdio");
    assert.equal(server.command, "uv");
    for (const flag of ["--frozen", "--no-sync", "--offline", "--no-python-downloads", "--no-env-file"]) {
      assert.ok(server.args.includes(flag), `${name} must retain ${flag}`);
    }
    assert.equal(server.args[server.args.indexOf("python") + 1], "-B");
    assert.equal(server.env.UV_PROJECT_ENVIRONMENT, "${PLUGIN_DATA}/runtime");
    assert.equal(server.args[server.args.indexOf("--python") + 1], "${PLUGIN_DATA}/runtime");
    assert.ok(!Object.hasOwn(server.env, "PLUGIN_DATA"), "Host-reserved PLUGIN_DATA must not be redefined.");
    assert.equal(server.env.PYTHONDONTWRITEBYTECODE, "1");
    assert.equal(server.args.at(-1), name === "comfyui" ? "official" : "companion");
  }
});

test("an absent runtime is rejected by uv without creating a virtual environment", async (t) => {
  const uv = spawnSync("uv", ["--version"], { encoding: "utf8" });
  if (uv.status !== 0) {
    t.skip("uv is absent; the prepared-runtime startup scenario is NOT_RUN here.");
    return;
  }
  const directory = await mkdtemp(path.join(os.tmpdir(), "comfy-missing-runtime-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const manifest = JSON.parse(await readFile(path.join(ROOT, "mcp.json"), "utf8"));
  const server = manifest.mcpServers.comfyui;
  const expand = (value) => value.replaceAll("${PLUGIN_ROOT}", ROOT).replaceAll("${PLUGIN_DATA}", directory);
  const result = spawnSync(server.command, server.args.map(expand), {
    cwd: ROOT, encoding: "utf8", timeout: 30_000,
    env: { ...process.env, PLUGIN_DATA: directory, ...Object.fromEntries(Object.entries(server.env).map(([key, value]) => [key, expand(value)])) },
  });
  assert.equal(result.status, 2, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stderr, /(?:No interpreter|not found|does not exist)/i);
  assert.doesNotMatch(result.stderr, /(?:Downloading|Creating virtual environment)/);
  await assert.rejects(stat(path.join(directory, "runtime")), { code: "ENOENT" });
});

// Check the committed uv serialization without a TOML dependency. Validate each
// registry sdist/wheel, never just one hash somewhere in a package block.
function checkMetadata(projectText, lockText) {
  const project = projectText.replaceAll("\r\n", "\n").split(/^\[project\]\s*$/m)[1]?.split(/^\[/m)[0];
  assert.ok(project, "project table is required");
  const array = project.match(/^dependencies\s*=\s*(\[[\s\S]*?\])/m)?.[1];
  assert.ok(array, "direct dependency array is required");
  assert.deepEqual(JSON.parse(array.replace(/,\s*\]/g, "]")), Object.entries(PINNED).map(([name, version]) => name + "==" + version));
  const packages = lockText.replaceAll("\r\n", "\n").split(/^\[\[package\]\]\s*$/m).slice(1);
  assert.ok(packages.length > Object.keys(PINNED).length);
  for (const [name, version] of Object.entries(PINNED)) {
    const item = packages.find((block) => block.match(/^name = "([^"]+)"$/m)?.[1] === name);
    assert.equal(item?.match(/^version = "([^"]+)"$/m)?.[1], version);
  }
  for (const item of packages.filter((block) => /^source = \{ registry = /m.test(block))) {
    const name = item.match(/^name = "([^"]+)"$/m)?.[1];
    const wheels = item.match(/^wheels = \[([\s\S]*?)^\]/m)?.[1] ?? "";
    const sdist = item.match(/^sdist = (\{[^\n]*\})$/m)?.[1] ?? "";
    const artifacts = [...(wheels + "\n" + sdist).matchAll(/\{[^{}]*\}/g)].map((match) => match[0]);
    assert.ok(artifacts.length > 0, name + " needs an actual registry artifact");
    for (const artifact of artifacts) {
      const hash = artifact.match(/\bhash = "([^"]*)"/)?.[1];
      assert.match(hash ?? "", /^sha256:[a-f0-9]{64}$/, name + " has an invalid artifact hash");
    }
  }
}

test("real lock records exact direct versions and every hashed transitive artifact", async () => {
  checkMetadata(await readFile(path.join(RUNTIME, "pyproject.toml"), "utf8"), await readFile(path.join(RUNTIME, "uv.lock"), "utf8"));
});

test("metadata checks reject extra dependencies and unhashed or corrupt wheels", async () => {
  const project = await readFile(path.join(RUNTIME, "pyproject.toml"), "utf8");
  const lock = await readFile(path.join(RUNTIME, "uv.lock"), "utf8");
  assert.throws(() => checkMetadata(project.replace('"mcp==2.0.0",', '"mcp==2.0.0", "extra==1.0.0",'), lock));
  const wheel = lock.match(/\.whl", hash = "sha256:[a-f0-9]{64}"/)?.[0];
  assert.ok(wheel);
  assert.throws(() => checkMetadata(project, lock.replace(wheel, wheel.replace(/sha256:[a-f0-9]{64}/, "invalid"))));
  assert.throws(() => checkMetadata(project, lock.replace(wheel, wheel.replace(/, hash = "[^"]*"/, ""))));
});

function existingPython() {
  const candidates = process.env.COMFYUI_TEST_PYTHON
    ? [process.env.COMFYUI_TEST_PYTHON]
    : process.platform === "win32" ? ["python", "python3"] : ["python3", "python"];
  return candidates.find((command) => {
    const probe = spawnSync(command, ["-I", "-B", "-c", "import sys; assert sys.version_info >= (3,10)"], { encoding: "utf8" });
    return probe.status === 0;
  });
}

test("configuration and startup fail closed without installing dependencies", (t) => {
  const python = existingPython();
  if (!python) {
    t.skip("A compatible existing Python is not available in this authoring environment; runtime behavior is NOT_RUN here.");
    return;
  }
  const code = `
import contextlib, importlib, io, json, os, sys, tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, ${JSON.stringify(RUNTIME)})
from config import ConfigurationError, child_environment, load_config, normalize_server_url, validate_config
import launcher, prepare_runtime
assert launcher.PINNED == prepare_runtime.PINNED == {'comfy-mcp':'0.10.0','comfy-cli':'1.22.0','mcp':'2.0.0'}

with tempfile.TemporaryDirectory(prefix='comfy-runtime-test-') as temporary:
    root = Path(temporary)
    core = root / 'core'
    core.mkdir()
    (core / 'main.py').write_text('# fixture', encoding='utf-8')
    (core / 'nodes.py').write_text('# fixture', encoding='utf-8')
    (core / 'comfy').mkdir()
    (core / 'comfy_extras').mkdir()
    data = root / 'data'
    data.mkdir()
    document = {'schema_version':1,'server_url':'http://127.0.0.1:8188/','workspace':str(core),'user_id':None}
    (data / 'config.json').write_text(json.dumps(document), encoding='utf-8')
    config = load_config(data)
    assert isinstance(config['workspace'], Path) and config['workspace'] == core
    assert config['server_url'] == 'http://127.0.0.1:8188'
    assert config['user_id'] is None
    for url in ['https://127.0.0.1:8188','https://localhost:8188','http://127.0.0.1','http://localhost','http://[::1]','http://127.0.0.1:','http://example.com:8188','http://0.0.0.0:8188','http://192.168.1.2:8188','http://127.0.0.1:0','http://user:secret@127.0.0.1:8188','http://127.0.0.1:8188/api','http://127.0.0.1:8188/?token=x']:
        try: normalize_server_url(url)
        except ConfigurationError: pass
        else: raise AssertionError('invalid endpoint accepted: ' + url)
    assert normalize_server_url('http://[::1]:8188') == 'http://[::1]:8188'
    env = child_environment(config, {'PATH':'retained','COMFY_LOCAL_URL':'http://localhost:9000','COMFYUI_URL':'http://remote','COMFYUI_HOST':'remote','COMFYUI_PORT':'9999','COMFY_API_KEY':'private','COMFY_PROJECT':'wrong','COMFY_MCP_ASSUME_CONSENT':'all','COMFY_CLOUD_BASE_URL':'https://remote','UV_PYTHON':'wrong','PYTHONPATH':'wrong'})
    assert env['PATH'] == 'retained'
    assert env['COMFY_BIN'] == str(config['comfy_bin'])
    assert 'COMFY_PROJECT' not in env
    assert env['COMFY_LOCAL_URL'] == config['server_url']
    assert env['UV_PROJECT_ENVIRONMENT'] == str(data / 'runtime')
    for key in ['COMFYUI_URL','COMFYUI_HOST','COMFYUI_PORT','COMFY_API_KEY','COMFY_MCP_ASSUME_CONSENT','COMFY_CLOUD_BASE_URL','UV_PYTHON','PYTHONPATH']: assert key not in env
    for key in ['DO_NOT_TRACK','COMFY_NO_TELEMETRY','COMFY_KNOWLEDGE_DISABLE','PYTHONDONTWRITEBYTECODE']: assert env[key] == '1'
    before = set(data.iterdir())
    with patch.object(launcher.sys, 'prefix', str(data / 'runtime')):
        try: launcher.check_runtime(config)
        except ConfigurationError as exc: assert 'preparation receipt' in str(exc)
        else: raise AssertionError('missing preparation receipt accepted')
    assert set(data.iterdir()) == before
    with patch.object(launcher, 'load_config', return_value=config), patch.object(launcher.sys, 'prefix', str(data / 'runtime')), patch.object(launcher.subprocess, 'run') as execute, contextlib.redirect_stderr(io.StringIO()):
        assert launcher.main(['official']) == 2
        execute.assert_not_called()
    receipt = {'schema_version':1,'status':'PREPARED','payload_sha256':{name:launcher.file_sha256(launcher.ROOT/name) for name in ('pyproject.toml','uv.lock')},'distributions':dict(launcher.PINNED)}
    config['comfy_bin'] = data / 'comfy-fixture'
    config['comfy_bin'].write_text('# fixture', encoding='utf-8')
    (data / 'runtime-receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
    with patch.object(launcher.sys, 'prefix', str(data / 'runtime')), patch.object(launcher.importlib.metadata, 'version', side_effect=lambda name:launcher.PINNED[name]):
        assert launcher.check_runtime(config)['status'] == 'PREPARED'
    receipt['payload_sha256']['uv.lock'] = '0' * 64
    (data / 'runtime-receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
    with patch.object(launcher.sys, 'prefix', str(data / 'runtime')):
        try: launcher.check_runtime(config)
        except ConfigurationError as exc: assert 'lock changed' in str(exc)
        else: raise AssertionError('changed runtime lock accepted')
    receipt['payload_sha256']['uv.lock'] = launcher.file_sha256(launcher.ROOT/'uv.lock')
    receipt['distributions']['transitive-fixture'] = '1.0.0'
    (data / 'runtime-receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
    with patch.object(launcher.sys, 'prefix', str(data / 'runtime')), patch.object(launcher.importlib.metadata, 'version', side_effect=lambda name: launcher.PINNED[name] if name in launcher.PINNED else '2.0.0'):
        try: launcher.check_runtime(config)
        except ConfigurationError as exc: assert 'differs from the prepared lock' in str(exc)
        else: raise AssertionError('changed transitive version accepted')
    (data / 'runtime-receipt.json').write_text('[]', encoding='utf-8')
    with patch.object(launcher.sys, 'prefix', str(data / 'runtime')):
        try: launcher.check_runtime(config)
        except ConfigurationError as exc: assert 'receipt is invalid' in str(exc)
        else: raise AssertionError('malformed receipt accepted')
    missing_data = root / 'uncreated'
    with patch.object(prepare_runtime.subprocess, 'run') as run, contextlib.redirect_stderr(io.StringIO()):
        assert prepare_runtime.main(['--data-dir',str(missing_data),'--python',str(root/'missing-python'),'--workspace',str(core)]) == 2
        run.assert_not_called()
    assert not missing_data.exists()
    for invalid_url in ('https://127.0.0.1:8188','http://127.0.0.1','http://[::1]'):
        with patch.object(prepare_runtime.subprocess, 'run') as run, contextlib.redirect_stderr(io.StringIO()):
            assert prepare_runtime.main(['--data-dir',str(missing_data),'--python',sys.executable,'--workspace',str(core),'--server-url',invalid_url]) == 2
            run.assert_not_called()
        assert not missing_data.exists()
    invalid = dict(document, workspace='relative/core')
    try: validate_config(invalid, data)
    except ConfigurationError: pass
    else: raise AssertionError('relative core accepted')
    (core / 'comfy_extras').rmdir()
    try: validate_config(document, data)
    except ConfigurationError: pass
    else: raise AssertionError('CLI-unrecognized core accepted')
print('PASS: local target, profile, environment, missing-runtime and invalid-Python boundaries')
`;
  const result = spawnSync(python, ["-I", "-B", "-c", code], {
    encoding: "utf8", timeout: 30_000, env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  });
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stdout, /^PASS:/);
});
