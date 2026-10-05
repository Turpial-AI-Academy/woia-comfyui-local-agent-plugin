import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

test("companion offline behavior: projects, profiles, revisions, conflicts, mappings and run evidence", () => {
  const candidates = process.env.COMFYUI_LOCAL_TEST_PYTHON
    ? [process.env.COMFYUI_LOCAL_TEST_PYTHON]
    : process.platform === "win32" ? ["python.exe", "python3.exe"] : ["python3", "python"];
  let selected;
  for (const command of candidates) {
    const result = spawnSync(command, ["-I", "-B", "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"], { encoding: "utf8" });
    if (!result.error && result.status === 0) {
      selected = command;
      break;
    }
  }
  assert.ok(selected, "Companion tests require an existing Python >=3.10; set COMFYUI_LOCAL_TEST_PYTHON. Tests never install an interpreter.");
  const result = spawnSync(selected, ["-I", "-B", "tests/fixtures/companion_tests.py", "-v"], {
    cwd: root,
    encoding: "utf8",
    timeout: 120_000,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
  });
  assert.equal(result.error, undefined, result.error?.message);
  assert.equal(result.status, 0, `${result.stdout ?? ""}\n${result.stderr ?? ""}`);
  assert.match(result.stderr, /Ran 29 tests/);
  assert.match(result.stderr, /\bOK\b/);
});
