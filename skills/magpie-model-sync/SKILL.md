---
name: magpie-model-sync
description: Sync the magpie provider block in ~/.pi/agent/models.json from Magpie's live /v1/models catalog, and audit model-scope (/scoped-models) coverage. Use when magpie models changed, when pi lists a missing/stale magpie model, after a magpie upgrade, or when checking that pi, magpie, and enabledModels agree.
metadata:
  requires: node 18+ (global fetch)
---

# Magpie ↔ Pi model sync

Magpie (`http://127.0.0.1:3425/v1`) is an OpenAI-compatible router; pi reaches it through the
`providers.magpie` block in `~/.pi/agent/models.json`, which is a **static snapshot** — pi never
discovers magpie models by itself. This skill audits and refreshes that snapshot.

Run scripts relative to this skill directory (`~/.pi/agent/skills/magpie-model-sync/`).

## Workflow

1. Audit first (read-only):
   `node scripts/sync-magpie-models.mjs --dry-run`
   It prints model count, added ids, removed ids and changed ids. `~ changed: 0` means pi is in sync.
2. Report the diff to the operator before writing. Writing `models.json` changes which models pi
   can select, so treat it as a config change, not a cache refresh.
3. Apply: `node scripts/sync-magpie-models.mjs`
   The script copies `models.json` to `models.json.bak.<ts>` before writing.
4. Verify: re-run with `--dry-run` → expect `~ changed: 0`, then check scope coverage (below).
5. Tell the operator to restart pi (or start a new session) so the new catalog is loaded.

## Options

- `--dry-run` — report only, never write.
- `--base-url <url>` — default `http://127.0.0.1:3425/v1`; override for a remote/other-port magpie.

There is also a stable alias: `~/.pi/agent/bin/pi-magpie-sync` (symlink to the script).

## Field mapping (magpie `/v1/models` → pi `models.json`)

| magpie | pi | Notes |
|---|---|---|
| `id` | `id` | identity; ids already carry the sub-provider prefix (`deepseek/…`, `groq/…`) |
| `magpie_label` (fallback `display_name`) | `name` | |
| `context_window` | `contextWindow` | omitted when magpie does not publish it |
| `max_output_tokens` | `maxTokens` | omitted when absent, never `null` |
| `modalities.input` ∩ {`text`,`image`} | `input` | pi models only text/image; falls back to `["text"]` |
| `reasoning` | `reasoning` | |
| `reasoning_levels` | `thinkingLevelMap` | `none→off`; `minimal/low/medium/high/xhigh/max` map to themselves; absent level → `null` |
| — | `cost` | magpie publishes no pricing; existing hand-maintained `cost` is preserved |

Pi-only/known gaps (do not "fix" by editing models.json):
- `video`, `audio`, `pdf` inputs reported by magpie are not representable in pi's `input`.
- Magpie's `default` thinking effort (e.g. `groq/qwen/qwen3.8-27b`) has no pi level.

## Model scope (`/scoped-models` ↔ `settings.json`)

`/scoped-models` is driven by `enabledModels` in `~/.pi/agent/settings.json`, matched with
case-insensitive `minimatch` against `provider/modelId` **and** bare `modelId`.

- All magpie models: `"enabledModels": ["magpie/**"]`
- **`magpie/*` matches nothing** — `*` does not cross `/`, so nested ids like
  `deepseek/deepseek-flash` fail. Always use `**`.
- `defaultProvider` + `defaultModel` must resolve into the scope, else startup selection breaks.
- New magpie models are picked up by an existing `magpie/**` pattern automatically; the audit below
  is still worth running to catch provider-level drift.

Coverage check (adjust the provider name if not magpie):

```sh
node -e '
const fs=require("fs"), {minimatch}=require(process.env.HOME+"/.pi/agent/npm/node_modules/minimatch");
const dir=process.env.HOME+"/.pi/agent";
const models=JSON.parse(fs.readFileSync(dir+"/models.json","utf8")).providers.magpie.models;
const pats=JSON.parse(fs.readFileSync(dir+"/settings.json","utf8")).enabledModels||[];
const hit=models.filter(m=>pats.some(p=>minimatch("magpie/"+m.id,p,{nocase:true})||minimatch(m.id,p,{nocase:true})));
console.log("scope:",pats.join(","),"matched:",hit.length+"/"+models.length);'
```

## Troubleshooting

- `GET …/models -> HTTP 502/503` or connection refused: magpie is not running / router still warming.
  The script fails loudly and writes nothing.
- `providers.magpie missing in models.json`: the provider block was removed; recreate it (at minimum
  `api: "openai-completions"`, `apiKey`, `baseUrl`) before syncing.
- Unknown model at request time (`model not found` from magpie): the id was removed upstream — run the
  audit, apply, then re-check `enabledModels`.
- Deeper per-field comparison against a saved catalog snapshot:
  `curl -s http://127.0.0.1:3425/v1/models > /tmp/magpie_models.json`, then diff `context_window`,
  `max_output_tokens`, `magpie_label`, `reasoning_levels` per `id` against `providers.magpie.models`.
- After editing this skill or `settings.json`, `/reload` in an active pi session.
