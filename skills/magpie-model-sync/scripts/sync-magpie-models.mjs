#!/usr/bin/env node
// Sync the `magpie` provider block in ~/.pi/agent/models.json from Magpie's
// live /v1/models catalog. Idempotent: unchanged fields produce no diff.
//
// Usage: pi-magpie-sync [--base-url http://127.0.0.1:3425/v1] [--dry-run]
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const AGENT_DIR = process.env.PI_CODING_AGENT_DIR || path.join(os.homedir(), ".pi", "agent");
const MODELS_PATH = path.join(AGENT_DIR, "models.json");
const PROVIDER = "magpie";
const PI_LEVELS = ["minimal", "low", "medium", "high", "xhigh", "max"];

const args = process.argv.slice(2);
const dryRun = args.includes("--dry-run");
const baseUrlIdx = args.indexOf("--base-url");
const baseUrl = (baseUrlIdx >= 0 ? args[baseUrlIdx + 1] : "http://127.0.0.1:3425/v1").replace(/\/+$/, "");

function thinkingLevelMap(entry) {
  if (!entry.reasoning) return undefined;
  const levels = new Set(entry.reasoning_levels || (entry.supported_reasoning_levels || []).map((l) => l.effort));
  if (levels.size === 0) return undefined;
  const map = {};
  for (const level of PI_LEVELS) map[level] = levels.has(level) ? level : null;
  map.off = levels.has("none") ? "none" : null;
  return map;
}

function toPiModel(entry, previous) {
  const modalities = (entry.modalities && entry.modalities.input) || [];
  const input = ["text", "image"].filter((m) => modalities.includes(m));
  const model = {
    id: entry.id,
    name: entry.magpie_label || entry.display_name || entry.id,
    input: input.length > 0 ? input : ["text"],
    reasoning: Boolean(entry.reasoning),
  };
  if (Number.isFinite(entry.context_window)) model.contextWindow = entry.context_window;
  if (Number.isFinite(entry.max_output_tokens)) model.maxTokens = entry.max_output_tokens;
  const tlm = thinkingLevelMap(entry);
  if (tlm) model.thinkingLevelMap = tlm;
  // Magpie publishes no pricing; keep whatever was hand-maintained before.
  if (previous?.cost) model.cost = previous.cost;
  return model;
}

const response = await fetch(`${baseUrl}/models`, { signal: AbortSignal.timeout(15000) });
if (!response.ok) throw new Error(`GET ${baseUrl}/models -> HTTP ${response.status}`);
const catalog = await response.json();
if (!Array.isArray(catalog.data)) throw new Error("unexpected /v1/models payload: missing data[]");

const raw = fs.readFileSync(MODELS_PATH, "utf8");
const config = JSON.parse(raw);
const provider = config.providers?.[PROVIDER];
if (!provider) throw new Error(`providers.${PROVIDER} missing in ${MODELS_PATH}`);

const previousById = new Map((provider.models || []).map((m) => [m.id, m]));
const nextModels = catalog.data.map((entry) => toPiModel(entry, previousById.get(entry.id)));

const before = provider.models || [];
const beforeIds = new Set(before.map((m) => m.id));
const afterIds = new Set(nextModels.map((m) => m.id));
const added = [...afterIds].filter((id) => !beforeIds.has(id));
const removed = [...beforeIds].filter((id) => !afterIds.has(id));
const changed = nextModels.filter((m) => {
  const prev = previousById.get(m.id);
  return !prev || JSON.stringify(sortKeys(prev)) !== JSON.stringify(sortKeys(m));
});

function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((k) => [k, sortKeys(value[k])]));
  }
  return value;
}

console.log(`provider: ${PROVIDER}  baseUrl: ${baseUrl}`);
console.log(`magpie models: ${nextModels.length}  (was ${before.length})`);
if (added.length) console.log(`+ new: ${added.join(", ")}`);
if (removed.length) console.log(`- gone: ${removed.join(", ")}`);
const fieldChanges = changed.filter((m) => previousById.has(m.id));
console.log(`~ changed: ${fieldChanges.length}${fieldChanges.length ? " (" + fieldChanges.map((m) => m.id).join(", ") + ")" : ""}`);

if (dryRun) {
  console.log("dry run: models.json not written");
  process.exit(0);
}

// Preserve catalog order but keep the previous order for models magpie still serves.
const ordered = [];
for (const id of beforeIds) {
  const found = nextModels.find((m) => m.id === id);
  if (found) ordered.push(found);
}
for (const model of nextModels) if (!beforeIds.has(model.id)) ordered.push(model);
provider.models = ordered;

const stamp = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14);
const backup = `${MODELS_PATH}.bak.${stamp}`;
fs.copyFileSync(MODELS_PATH, backup);
fs.writeFileSync(MODELS_PATH, `${JSON.stringify(config, null, 2)}\n`, "utf8");
console.log(`wrote ${MODELS_PATH} (backup: ${path.basename(backup)})`);
