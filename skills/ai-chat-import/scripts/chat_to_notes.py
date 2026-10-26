#!/usr/bin/env python3
"""AI 聊天会话导出 JSON → Obsidian 收件箱原文笔记（平台无关）。

输入形状：{sessions: [{id, title, updated_at, messages: [{role, ts, frags: [{type, text}]}]}]}
其中 role 为 USER / ASSISTANT，frags.type 为 REQUEST / RESPONSE / TEMPLATE_RESPONSE / THINK / TIP。

用法：
    python3 chat_to_notes.py --json export.json \
        --inbox "<vault>/04_归档（Archive）/02_AI会话" --account Gemini
    ... --write            # 真正写入；已存在的同源笔记原地覆盖
    ... --tag Gemini --today 2026-10-22 --source-base "https://gemini.google.com/app/"

默认 dry-run，只打印统计与一篇样例。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

BAD = {
    "|": "｜", ":": "：", "?": "？", "*": "＊", "/": "／", "\\": "＼",
    '"': "＂", "<": "＜", ">": "＞", "#": "＃",
}
FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"!?\[\[([^\]\n]+)\]\]")
SKIP_DIRS = {".git", ".obsidian", ".agents", ".jupymd", ".jupyter-env",
             ".ruff_cache", ".workbuddy-ai", "node_modules", "__pycache__"}

ARGS = None
NAMES = set()
FILES = set()


def build_index(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            FILES.add(f)
            if f.endswith(".md"):
                NAMES.add(f[:-3])


def resolves(target):
    base = target.split("/")[-1]
    if base in NAMES or base in FILES:
        return True
    return "/" in target and os.path.exists(os.path.join(ARGS.vault, target))


def escape_plain(seg):
    out, last = [], 0
    for m in LINK.finditer(seg):
        target = m.group(1).split("|")[0].split("#")[0].strip()
        if not target or resolves(target):
            continue
        out.append(seg[last:m.start()])
        out.append(m.group(0).replace("[[", "\\[\\[").replace("]]", "\\]\\]"))
        last = m.end()
    out.append(seg[last:])
    return "".join(out)


def escape_segment(seg):
    parts, last = [], 0
    for m in INLINE.finditer(seg):
        parts.append(escape_plain(seg[last:m.start()]))
        parts.append(m.group(0))
        last = m.end()
    parts.append(escape_plain(seg[last:]))
    return "".join(parts)


def escape_links(text):
    out, last = [], 0
    for m in FENCE.finditer(text):
        out.append(escape_segment(text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(escape_segment(text[last:]))
    return "".join(out)


def clean_title(raw):
    t = re.sub(r"\s+", " ", raw or "").strip()
    for k, v in BAD.items():
        t = t.replace(k, v)
    t = t.rstrip("。. ")
    if len(t) > ARGS.max_title:
        t = t[:ARGS.max_title].rstrip()
    return t or "未命名会话"


def fence_balance(text):
    return text + "\n```" if text.count("```") % 2 == 1 else text


def details(summary, body):
    return ["<details>", "<summary>%s</summary>" % summary, "",
            fence_balance(body), "", "</details>", ""]


def pick(frags, types):
    return "\n\n".join(
        f.get("text") or "" for f in frags
        if f.get("type") in types and (f.get("text") or "").strip()).strip()


def group_messages(msgs):
    """连续多条 assistant 合并进同一轮，避免出现重复的轮次标题。"""
    sections = []
    n = 0
    for m in msgs:
        frags = m.get("frags") or []
        if m["role"] == "USER":
            text = pick(frags, ("REQUEST",))
            if not text:
                continue
            n += 1
            sections.append({"n": n, "user": text, "resp": [], "aux": [], "think": []})
            continue
        resp = pick(frags, ("RESPONSE", "TEMPLATE_RESPONSE"))
        aux = pick(frags, ("SEARCH", "TOOL_SEARCH", "TOOL_OPEN", "TOOL_FIND", "TIP"))
        think = pick(frags, ("THINK",))
        if not (resp or aux or think):
            continue
        if not sections:
            n += 1
            sections.append({"n": n, "user": None, "resp": [], "aux": [], "think": []})
        cur = sections[-1]
        for key, val in (("resp", resp), ("aux", aux), ("think", think)):
            if val:
                cur[key].append(val)
    return [s for s in sections if s["user"] or s["resp"] or s["aux"] or s["think"]]


def render(sess):
    title = clean_title(sess["title"])
    date = datetime.fromtimestamp(sess["updated_at"]).strftime("%Y-%m-%d")
    sections = group_messages(sess["messages"])
    if not sections:
        return title, date, None

    src = "%s%s" % (ARGS.source_base, sess["id"])
    out = [
        "---",
        'title: "%s"' % title,
        'source: "%s"' % src,
        'account: "%s"' % ARGS.account,
        "published: %s" % date,
        "status: %s" % ("archived" if ARGS.layout == "archive" else "inbox"),
        "tags: [%s]" % ARGS.tag,
        "updated: %s" % ARGS.today,
        "by: agent",
        "---",
        "",
        "# %s" % title,
        "",
        "> %s 会话原文 · %s · %d 轮" % (ARGS.account, date, len(sections)),
        "",
    ]
    for s in sections:
        if s["user"]:
            out += ["## 第 %d 轮 · 我" % s["n"], "", fence_balance(s["user"]), ""]
        if s["resp"] or s["aux"] or s["think"]:
            out += ["## 第 %d 轮 · %s" % (s["n"], ARGS.account), ""]
            if s["resp"]:
                out += [fence_balance("\n\n".join(s["resp"])), ""]
            if s["aux"]:
                out += details("检索与提示", "\n\n".join(s["aux"]))
            if s["think"]:
                out += details("深度思考", "\n\n".join(s["think"]))
    return title, date, escape_links("\n".join(out).rstrip() + "\n")


def dest(month, base):
    """写入路径。archive：<root>/<平台>/<YYYY-MM>/YYYY-MM-DD - 标题.md；inbox：<root>/<YYYY-MM>/YYYY-MM-DD 标题.md。"""
    if ARGS.layout == "archive":
        return os.path.join(ARGS.inbox, ARGS.account, month, "%s - %s.md" % (base[0], base[1]))
    return os.path.join(ARGS.inbox, month, "%s %s.md" % base)


def existing_by_source():
    found = {}
    head = ARGS.source_base
    for root, _, names in os.walk(ARGS.inbox):
        for name in names:
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            try:
                text = open(path, encoding="utf-8").read(800)
            except OSError:
                continue
            if head in text:
                found[text.split(head)[1].split('"')[0]] = path
    return found


def main():
    global NAMES, FILES
    data = json.load(open(ARGS.json, encoding="utf-8"))
    sessions = sorted(data["sessions"], key=lambda s: s["updated_at"])
    build_index(ARGS.vault)
    existing = existing_by_source() if ARGS.write else {}

    used, plan, skipped = {}, [], 0
    for s in sessions:
        title, date, body = render(s)
        if body is None:
            skipped += 1
            continue
        month = date[:7]
        base = (date, title)
        if s["id"] in existing:
            path = existing[s["id"]]
        else:
            path = dest(month, base)
            key = (month, base)
            if key in used or os.path.exists(path):
                k = used.get(key, 1)
                while True:
                    k += 1
                    cand = dest(month, base)
                    stem, ext = os.path.splitext(cand)
                    cand = "%s（%d）%s" % (stem, k, ext)
                    if not os.path.exists(cand):
                        break
                used[key] = k
                path = cand
            else:
                used[key] = 1
        plan.append((path, body, month))

    dup = [p for p, _, _ in plan if os.path.basename(p).endswith("）.md")]
    print("sessions:", len(sessions), "-> notes:", len(plan), "skipped(empty):", skipped)
    print("bytes:", sum(len(b) for _, b, _ in plan))
    print("months:", len({m for _, _, m in plan}))
    print("in-place overwrite:", len(existing), " new suffixed:", len(dup))
    print("longest path bytes:", max([len(p.encode()) for p, _, _ in plan] or [0]))

    if not ARGS.write:
        print("\n--- sample: %s ---" % plan[0][0])
        print(plan[0][1][:900])
        print("\n(去掉 --write 只预览；加 --write 落盘)")
        return

    for path, body, _ in plan:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
    print("written:", len(plan))


def parse():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", required=True, help="导出的 sessions JSON 路径")
    p.add_argument("--inbox", required=True,
                   help="写入根目录。默认 layout=archive，指 <vault>/04_归档（Archive）/02_AI会话")
    p.add_argument("--layout", choices=("archive", "inbox"), default="archive",
                   help="archive（默认）：<root>/<平台>/YYYY-MM/YYYY-MM-DD - 标题.md；"
                        "inbox：<root>/YYYY-MM/YYYY-MM-DD 标题.md（历史行为，剪藏才用）")
    p.add_argument("--vault", help="库根目录，用于判定双链是否可解析（默认从 --inbox 向上找 .obsidian）")
    p.add_argument("--account", required=True, help="平台名，写进 frontmatter account 与助手节标题，如 DeepSeek / Gemini")
    p.add_argument("--tag", help="frontmatter tags 单值，默认与 --account 相同")
    p.add_argument("--today", help="frontmatter updated，默认今天")
    p.add_argument("--max-title", type=int, default=60, dest="max_title")
    p.add_argument("--source-base", default="https://chat.deepseek.com/a/chat/s/", dest="source_base")
    p.add_argument("--write", action="store_true")
    a = p.parse_args()
    if not a.today:
        a.today = datetime.now().strftime("%Y-%m-%d")
    if not a.tag:
        a.tag = a.account
    if not a.vault:
        cur = os.path.abspath(a.inbox.rstrip("/"))
        while True:
            if os.path.isdir(os.path.join(cur, ".obsidian")):
                a.vault = cur
                break
            parent = os.path.dirname(cur)
            if parent == cur:
                a.vault = os.path.dirname(os.path.abspath(a.inbox.rstrip("/")))
                break
            cur = parent
    if not os.path.isdir(a.inbox):
        sys.exit("写入目录不存在（先确保归档目录建好）：%s" % a.inbox)
    return a


if __name__ == "__main__":
    ARGS = parse()
    main()
