import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const ROOT = path.resolve(import.meta.dirname, "..");
const SKILL_ROOT = path.join(ROOT, "skills", "comfyui-local");
const ROUTES_FILE = path.join(SKILL_ROOT, "assets", "guide-routes.json");

test("every advertised task route resolves to a packaged guide accessible from the skill", async () => {
  const catalog = JSON.parse(await readFile(ROUTES_FILE, "utf8"));
  const skill = await readFile(path.join(SKILL_ROOT, "SKILL.md"), "utf8");
  const index = await readFile(path.join(SKILL_ROOT, "references", "README.md"), "utf8");
  assert.equal(catalog.schema, "comfyui-local-guide-routes/1");
  assert.equal(catalog.capability_source, "connected-server-schemas-and-models");
  assert.equal(new Set(catalog.routes.map((route) => route.id)).size, catalog.routes.length);
  for (const route of catalog.routes) {
    assert.ok(["guidance","conditional-local-modality","local-tool-operation"].includes(route.kind));
    const guide = path.resolve(path.dirname(ROUTES_FILE), route.guide);
    const relative = path.relative(SKILL_ROOT, guide);
    assert.ok(!relative.startsWith("..") && !path.isAbsolute(relative), route.id + " escapes the skill");
    assert.equal(path.extname(guide), ".md");
    await access(guide);
    assert.ok(skill.includes("](" + relative.split(path.sep).join("/") + ")"), route.id + " cannot be discovered from SKILL.md");
    assert.ok(index.includes("](" + path.basename(guide) + ")"), route.id + " is absent from the guide index");
  }
});

test("the documented companion tool contract matches the implemented public tool inventory", async () => {
  const catalog = JSON.parse(await readFile(ROUTES_FILE, "utf8"));
  const source = await readFile(path.join(ROOT, "plugin-resources", "runtime", "companion.py"), "utf8");
  const toolNames = [...source.matchAll(/@mcp\.tool\(\)\s+(?:async\s+)?def\s+(\w+)\s*\(/g)].map((match) => match[1]);
  assert.equal(new Set(toolNames).size, toolNames.length);
  assert.deepEqual([...catalog.companion_tools].sort(), [...toolNames].sort());
  const manifest = JSON.parse(await readFile(path.join(ROOT, "mcp.json"), "utf8"));
  assert.deepEqual(Object.keys(manifest.mcpServers).sort(), ["comfyui","comfyui-projects"]);
});

test("discoverable skill metadata remains aligned with the WOIA plugin", async () => {
  const manifest = JSON.parse(await readFile(path.join(ROOT, "plugin.json"), "utf8"));
  const skill = await readFile(path.join(SKILL_ROOT, "SKILL.md"), "utf8");
  assert.match(skill, /^name:\s*comfyui-local$/m);
  assert.match(skill, new RegExp('version:\\s*"' + manifest.version.replaceAll(".", "\\.") + '"'));
  assert.match(skill, /^license:\s*MIT$/m);
  assert.match(skill, /^compatibility:\s*\S.+$/m);
  assert.doesNotMatch(skill, /^allowed-tools:/m);
});

test("optional output templates are discoverable and remain inside the skill payload", async () => {
  const index = await readFile(path.join(SKILL_ROOT, "assets", "README.md"), "utf8");
  for (const template of ["creative-brief.template.md","shot-plan.template.md","run-review.template.md"]) {
    await access(path.join(SKILL_ROOT, "assets", template));
    assert.ok(index.includes("](" + template + ")"), template + " has no declared purpose");
  }
});
