#!/usr/bin/env python3
"""~/.agents/skills 是自写技能的仓库。分发权归 magpie，这里只管 magpie 不认识的 agent。

分工（2026-10-22 起）：

  ~/.agents/skills/<名>                       自写技能的真身
  ~/.config/magpie/library/skills/<名>         上游技能的真身（grill-me、diagram-design）
  magpie library sync                         把库写进 pi / workbuddy / qoder
  make link                                   只管 lmstudio（magpie 没有这个 agent）

为什么不复制：同一份技能改一次要在六处同步，必然漂移。
为什么不把真身放进 magpie 库：那是 app 私有目录，`magpie library skill rm --all` 一键清空、
GitHub 源技能 `update --replace-edits` 会覆盖手改。自写的技能不放进被应用管理生命周期的目录。

用法见 make help。所有改动都可逆：真身没被删过，软链删了 make link / magpie library sync 就回来。
"""

import json
import os
import shutil
import sys

HOME = os.path.expanduser("~")
CENTER = os.path.join(HOME, ".agents", "skills")
LIBRARY = os.path.join(HOME, ".config", "magpie", "library", "skills")
LIBRARY_JSON = os.path.join(HOME, ".config", "magpie", "library.json")
MAGPIE = "/Applications/Magpie.app/Contents/MacOS/magpie"

# magpie 能认的 agent：分发归 magpie，这里只读不写（左边是这里的标签，右边是 magpie 的 id）
MAGPIE_AGENTS = [
    ("pi", "pi", os.path.join(HOME, ".pi", "agent", "skills")),
    ("workbuddy", "workbuddy-ai", os.path.join(HOME, ".workbuddy-ai", "skills")),
    ("qoder", "qoder", os.path.join(HOME, ".qoder", "skills")),
    # alma / omp 已于 2026-10-22 弃用（app 不在了，目录也删了）
]

# magpie 不认识的 agent：仍由 make link 铺
SELF_AGENTS = [
    ("lmstudio", None, os.path.join(HOME, ".lmstudio", "skills")),
]

# 真身托管在别处的技能：真身在 magpie 库，仓库里不放指针（避免两级软链）
EXTERNAL = {
    "grill-me": os.path.join(LIBRARY, "grill-me"),
}


def skills():
    """仓库里的技能名 + 真身托管在别处的技能。"""
    names = set(EXTERNAL)
    if os.path.isdir(CENTER):
        names.update(d for d in os.listdir(CENTER)
                     if os.path.isdir(os.path.join(CENTER, d)))
    return sorted(names)


def body(name):
    """技能真身在哪。托管在别处的跟着上游走。"""
    return EXTERNAL.get(name, os.path.join(CENTER, name))


def link_target(name):
    """要铺的软链指向哪。"""
    return body(name)


def managed_roots():
    """算「自己建的软链」的两个根：仓库 + magpie 库。"""
    return [CENTER, LIBRARY]


def link_dest(path):
    """软链解析到的绝对路径；不是软链返回 None。"""
    if not os.path.islink(path):
        return None
    raw = os.readlink(path)
    target = raw if os.path.isabs(raw) else os.path.join(os.path.dirname(path), raw)
    return os.path.abspath(target)


def under(path, root):
    return path is not None and (path == root or path.startswith(root + os.sep))


def is_managed_link(path):
    """只认指向仓库或 magpie 库的软链。真实目录、普通文件、指向别处的软链一律不碰。"""
    dest = link_dest(path)
    return any(under(dest, r) for r in managed_roots())


def is_ours(path):
    """指向仓库（不是 magpie 库）的软链才算这里建的。库里的技能归 magpie 记账。"""
    return under(link_dest(path), CENTER)


def all_agents():
    return MAGPIE_AGENTS + SELF_AGENTS


def magpie_applied():
    """magpie 认为每个 agent 该有哪些技能。读不到就返回 None（降级，不报错）。"""
    try:
        with open(LIBRARY_JSON, encoding="utf-8") as fh:
            applied = json.load(fh).get("applied", {})
    except (OSError, ValueError):
        return None
    return {a: set(v.get("skills", [])) for a, v in applied.items()}


def cmd_link():
    """只铺 magpie 不认识的 agent。magpie 管的那些用 magpie library sync。"""
    names = skills()
    if not names:
        print("仓库是空的：%s" % CENTER)
        return 1
    synced = 0
    for label, _, adir in SELF_AGENTS:
        if not os.path.isdir(adir):
            print("  跳过 %-10s 未安装" % label)
            continue
        synced += 1
        linked, conflicts, pruned = 0, [], []
        for name in names:
            dst = os.path.join(adir, name)
            if os.path.islink(dst):
                os.unlink(dst)
            elif os.path.exists(dst):
                conflicts.append(name)
                continue
            os.symlink(link_target(name), dst)
            linked += 1
        for entry in sorted(os.listdir(adir)):
            p = os.path.join(adir, entry)
            if is_ours(p) and entry not in names:
                os.unlink(p)
                pruned.append(entry)
        msg = "  %-10s 链了 %d 个" % (label, linked)
        if pruned:
            msg += "，清掉失效软链 %s" % "、".join(pruned)
        if conflicts:
            msg += "，跳过已有实体 %s" % "、".join(conflicts)
        print(msg)
    print("\n共 %d 个技能，%d 个 agent 目录已同步。" % (len(names), synced))
    print("其余 agent 归 magpie：改完技能跑 %s library sync" % "magpie")
    print("技能在会话启动时扫描，改完要重开会话才生效。")
    return 0


def cmd_status():
    names = skills()
    print("仓库：%s（%d 个技能）" % (CENTER.replace(HOME, "~"), len(names)))
    print("托管：%s" % "、".join("%s→magpie 库" % n for n in sorted(EXTERNAL)))
    print()
    width = max([len(n) for n in names] + [4])
    head = "  %-*s" % (width, "技能")
    for label, _, _ in all_agents():
        head += " %-10s" % (label + "*" if label != "lmstudio" else label)
    print(head)
    print("  （* 归 magpie 管，make link 不碰）")
    for name in names:
        row = "  %-*s" % (width, name)
        for _, _, adir in all_agents():
            if not os.path.isdir(adir):
                row += " %-10s" % "-"
                continue
            p = os.path.join(adir, name)
            if os.path.islink(p):
                row += " %-10s" % ("ok" if os.path.exists(p) else "断链")
            elif os.path.isdir(p):
                row += " %-10s" % "实体副本"
            else:
                row += " %-10s" % "缺"
        print(row)

    stale, library_own = [], set()
    for label, _, adir in all_agents():
        if not os.path.isdir(adir):
            continue
        for entry in sorted(os.listdir(adir)):
            p = os.path.join(adir, entry)
            if is_ours(p) and entry not in names:
                stale.append("%s/%s" % (label, entry))
            elif under(link_dest(p), LIBRARY) and entry not in names:
                library_own.add(entry)
    if stale:
        print("\n失效软链（仓库里已没有这个技能）：%s" % "、".join(stale))
        print("清理：make link（只清 lmstudio）")
    if library_own:
        print("\nmagpie 库自己的技能（不归这里，别 make link）：%s"
              % "、".join(sorted(library_own)))

    # 两套机制之间的漂移：magpie 的账本 vs 实际软链
    applied = magpie_applied()
    if applied is not None:
        drift = []
        for label, mid, adir in MAGPIE_AGENTS:
            if not os.path.isdir(adir):
                continue
            expected = applied.get(mid, set())
            for name in names:
                has = os.path.islink(os.path.join(adir, name))
                if name in expected and not has:
                    drift.append("%s 该有 %s 但没有" % (label, name))
                elif has and name not in expected:
                    drift.append("%s 有 %s 但 magpie 账本没有" % (label, name))
        if drift:
            print("\n漂移（magpie 账本与实际软链不一致）：")
            for d in drift:
                print("  - %s" % d)
            print("修：magpie library sync，或 magpie library skill agents <技能> <agents>")
    return 0


def cmd_check():
    """技能能否被 agent 加载：目录 + SKILL.md + name/description frontmatter + 名字一致。"""
    bad = 0
    names = skills()
    for name in names:
        path = body(name)
        skill_md = os.path.join(path, "SKILL.md")
        if not os.path.exists(skill_md):
            print("  [ERROR] %-20s 缺 SKILL.md（%s）" % (name, path.replace(HOME, "~")))
            bad += 1
            continue
        text = open(skill_md, encoding="utf-8", errors="replace").read()
        if not text.startswith("---"):
            print("  [ERROR] %-20s SKILL.md 不以 frontmatter 开头" % name)
            bad += 1
            continue
        fm = text.split("---", 2)[1]
        fields = {}
        for line in fm.splitlines():
            if ":" in line and not line.startswith((" ", "\t")):
                k, v = line.split(":", 1)
                fields[k.strip()] = v.strip()
        missing = [k for k in ("name", "description") if not fields.get(k)]
        if missing:
            print("  [ERROR] %-20s frontmatter 缺 %s" % (name, "、".join(missing)))
            bad += 1
        elif fields["name"] != name:
            print("  [ERROR] %-20s name=%s 与目录名不一致" % (name, fields["name"]))
            bad += 1
    print("\n%d 个技能，%d 个问题。" % (len(names), bad))
    return 0 if bad == 0 else 1


def cmd_import(src):
    src = os.path.abspath(os.path.expanduser(src))
    if not os.path.isdir(src):
        print("不是目录：%s" % src)
        return 1
    name = os.path.basename(src.rstrip(os.sep))
    dst = os.path.join(CENTER, name)
    if os.path.lexists(dst):
        print("仓库里已有同名技能：%s。先改名或先删，不覆盖。" % name)
        return 1
    shutil.move(src, dst)
    print("已收进仓库：%s" % name)
    rc = cmd_link()
    print()
    print("还要让 magpie 认它（CLI 装不了技能，只能用 app 的 Library 页）：")
    print("  1. app › Library › 添加技能 › 文件夹，选 %s" % dst.replace(HOME, "~"))
    print("  2. magpie library skill agents %s pi,workbuddy-ai,qoder" % name)
    print("  3. magpie library sync")
    return rc


def cmd_unlink(name):
    n = 0
    for label, _, adir in all_agents():
        p = os.path.join(adir, name)
        if is_managed_link(p):
            os.unlink(p)
            n += 1
            print("  已解除 %s" % label)
    if n == 0:
        print("没有任何 agent 链着 %s" % name)
    if name in EXTERNAL:
        print("真身在 magpie 库：%s，跟着上游走，别搬。" % EXTERNAL[name].replace(HOME, "~"))
        print("要连 magpie 账本一起退：magpie library skill agents %s none" % name)
    else:
        print("真身仍在 %s，要删自己删。" % os.path.join(CENTER, name).replace(HOME, "~"))
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    cmd = args[0]
    if cmd == "link":
        return cmd_link()
    if cmd == "status":
        return cmd_status()
    if cmd == "check":
        return cmd_check()
    if cmd == "import" and len(args) > 1:
        return cmd_import(args[1])
    if cmd == "unlink" and len(args) > 1:
        return cmd_unlink(args[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
