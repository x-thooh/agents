#!/usr/bin/env python3
"""Local custom-engine adapter: skill-up -> magpie (OpenAI-compatible), no CLI agent.

Implements the skill-up Custom Engine `local` transport contract:
  reads SessionInput from --input, drives a tool loop against magpie,
  writes SessionResult JSON to --output.

Env:
  MAGPIE_BASE_URL (default http://127.0.0.1:3425/v1)
  MAGPIE_API_KEY  (default "magpie")
  MAGPIE_MODEL    (default deepseek/deepseek-flash)
  HARNESS_SKILL_DIR  optional: directory holding SKILL.md to inject as system contract
  SKILLUP_MAX_STEPS  optional tool-loop cap (default 40)
"""

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE_URL = os.environ.get("MAGPIE_BASE_URL", "http://127.0.0.1:3425/v1").rstrip("/")
API_KEY = os.environ.get("MAGPIE_API_KEY", "magpie")
MODEL = os.environ.get("MAGPIE_MODEL", "deepseek/deepseek-flash")
MAX_STEPS = int(os.environ.get("SKILLUP_MAX_STEPS", "40"))
SKILL_DIR = os.environ.get("HARNESS_SKILL_DIR", "")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer", "description": "1-based start line"},
                    "limit": {"type": "integer", "description": "max lines, default 400"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file in the workspace with exact content.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files under a workspace directory (max depth 3).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command in the workspace root and return combined output.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]


def log(msg):
    print(f"[magpie-agent] {msg}", file=sys.stderr, flush=True)


def chat(messages, tools):
    """POST /chat/completions with bounded retries on transient upstream noise.

    magpie sometimes returns an empty or non-JSON body on a 200 under load.
    Crash-free: after retries, raises ChatError so main() emits a clean
    SessionResult instead of a traceback.
    """
    body = json.dumps({"model": MODEL, "messages": messages, "tools": tools}).encode()
    last = "unknown error"
    for attempt in range(1, 5):
        try:
            req = urllib.request.Request(
                BASE_URL + "/chat/completions",
                data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
            )
            with urllib.request.urlopen(req, timeout=900) as resp:
                text = resp.read().decode(errors="replace")
            if not text.strip():
                raise ValueError("empty response body")
            data = json.loads(text)
            choice = (data.get("choices") or [{}])[0].get("message")
            if choice is None:
                raise ValueError(f"no choices in response: {text[:200]}")
            return data
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
            if e.code not in (408, 425, 429, 500, 502, 503, 504):
                raise ChatError(last) from None
        except (ValueError, json.JSONDecodeError, urllib.error.URLError, TimeoutError) as e:
            last = f"{type(e).__name__}: {e}"
        if attempt < 4:
            wait = 3 * attempt
            log(f"chat attempt {attempt} failed ({last[:120]}); retry in {wait}s")
            time.sleep(wait)
    raise ChatError(last)


class ChatError(RuntimeError):
    pass


def resolve(ws, p):
    target = (ws / p).resolve() if not os.path.isabs(p) else pathlib.Path(p).resolve()
    if ws not in target.parents and target != ws:
        raise ValueError(f"path escapes workspace: {p}")
    return target


# Eval hygiene: the agent under test must not read the skill's own source tree or
# its eval suite (cases/scripts) — that is the grader. File tools already refuse
# escapes via resolve(); run_shell did not, so the first real run had the model
# browsing /Users/.../harness-bootstrap/evals/cases. Fail closed here, visibly.
ALLOWED_ABS_PREFIXES = (
    "/dev/null",
    "/dev/stdout",
    "/dev/stderr",
    "/bin/",
    "/usr/bin/",
    "/usr/local/bin/",
)


def contain_violation(cmd, ws):
    """Return a refusal reason for commands that leave the workspace, else ''."""
    if re.search(r"(^|[\s'\"=;(/])\.\.(/|$|[\s'\");])", cmd):
        return "command contains '..' as a path segment; the sandbox is limited to the workspace root"
    for tok in re.findall(r"(?<![\w.\-/])(/[^\s'\";|&()<>]*)", cmd):
        if tok.startswith(str(ws)):
            continue
        if any(tok == p or tok.startswith(p) for p in ALLOWED_ABS_PREFIXES):
            continue
        return f"absolute path outside the workspace is not allowed: {tok}"
    if re.search(r"(^|[\s=:\"'])[~]", cmd):
        return "home-directory paths are not allowed; the workspace root is the only tree"
    return ""


def run_tool(ws, name, args):
    try:
        if name == "read_file":
            f = resolve(ws, args["path"])
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            offset = max(1, int(args.get("offset") or 1))
            limit = int(args.get("limit") or 400)
            chunk = lines[offset - 1 : offset - 1 + limit]
            return "\n".join(f"{i + offset}\t{l}" for i, l in enumerate(chunk))
        if name == "write_file":
            f = resolve(ws, args["path"])
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(args["content"], encoding="utf-8")
            return f"wrote {len(args['content'])} chars to {args['path']}"
        if name == "list_files":
            base = resolve(ws, args.get("path") or ".")
            out = []
            for root, dirs, files in os.walk(base):
                depth = len(pathlib.Path(root).relative_to(base).parts)
                if depth >= 3:
                    dirs[:] = []
                for d in sorted(dirs):
                    if d.startswith(".git"):
                        continue
                    out.append(str(pathlib.Path(root, d).relative_to(ws)) + "/")
                for f in sorted(files):
                    out.append(str(pathlib.Path(root, f).relative_to(ws)))
            return "\n".join(out[:400]) or "(empty)"
        if name == "run_shell":
            violation = contain_violation(args["command"], ws)
            if violation:
                return f"REFUSED: {violation}"
            p = subprocess.run(
                args["command"], shell=True, cwd=ws, capture_output=True, text=True, timeout=600
            )
            out = (p.stdout or "") + (p.stderr or "")
            return f"exit={p.returncode}\n{out[-8000:]}"
        return f"unknown tool {name}"
    except Exception as e:  # noqa: BLE001
        return f"tool error: {type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    session = json.loads(pathlib.Path(a.input).read_text(encoding="utf-8"))
    ws = pathlib.Path(session.get("workspace") or os.getcwd()).resolve()
    # Runtime scaffolding under a hidden dir: created up front so the agent under
    # test sees them from step 1 and can register them, instead of outputs/
    # materializing only after the final message (which would look like a new
    # unregistered dir at judge time).
    (ws / ".skillup" / "inputs").mkdir(parents=True, exist_ok=True)
    (ws / ".skillup" / "outputs").mkdir(parents=True, exist_ok=True)
    messages: list[dict] = list(session.get("messages") or [])
    if not messages:
        messages = [{"role": "user", "content": os.environ.get("MAGPIE_PROMPT", "")}]

    system = [
        "You are an autonomous coding agent operating inside a workspace.",
        f"Workspace root: {ws}",
        "Use tools to inspect and modify files. Paths are relative to the workspace root.",
        "Stay inside the workspace root: reading the skill's own source tree or its eval suite is out of scope.",
        "Do the work yourself; do not ask the user questions. When finished, reply with a concise summary of what you changed and how you verified it.",
    ]
    if SKILL_DIR:
        skill_md = pathlib.Path(SKILL_DIR) / "SKILL.md"
        if skill_md.is_file():
            system.append("\n--- SKILL CONTRACT (follow it) ---\n" + skill_md.read_text(encoding="utf-8"))
    messages = [{"role": "system", "content": "\n".join(system)}] + messages

    final = ""
    for step in range(MAX_STEPS):
        try:
            resp = chat(messages, TOOLS)
        except ChatError as e:
            detail = str(e)[:800]
            log(f"giving up at step {step + 1}: {detail}")
            pathlib.Path(a.output).parent.mkdir(parents=True, exist_ok=True)
            pathlib.Path(a.output).write_text(
                json.dumps(
                    {"exit_code": 1, "final_message": f"magpie call failed: {detail}", "stderr": detail},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return 1
        msg = resp["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        messages.append(
            {
                "role": "assistant",
                "content": msg.get("content") or "",
                **({"tool_calls": calls} if calls else {}),
            }
        )
        if not calls:
            final = msg.get("content") or ""
            break
        for c in calls:
            fn = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            out = run_tool(ws, fn, args)
            log(f"step {step + 1}: {fn}({args.get('path') or args.get('command', '')[:60]})")
            messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": out[:12000]})
    else:
        final = final or "(max steps reached without a final answer)"

    result = {"exit_code": 0, "final_message": final}
    pathlib.Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
