"""baseline: 老账账本（`.harness/baseline.txt` + `.harness/accepted.json`）。

规格在 `AGENTS.md`「硬规则」与 `.harness/specs/standards.md`；本文件是执行侧。

  BASE011  账本格式坏，或 accepted 条目缺必填字段（理由 / 负责人 / 复查日期）
  BASE012  accepted 的复查日期已过期而未续期（过期豁免 = 必须重新盖章）
  BASE013  总数上升（有 git 时比对 HEAD 里的账本；没有 git 时记 WARN，不冒充通过）
  BASE014  条数下降，可以刷新账本（WARN，不是错）

「新欠」不单独占一个 code：它沿用**原来那条发现的 code**，只把消息前缀写成「新欠」。
换一个 code 会让调用方失去过滤能力（`--scope`、按 code 忽略都失效），而账本的作用是
判断「这批老账有没有变大」，不是重新命名问题。账本内的一律降成 WARN，消息前缀「基线内」。

指纹 = `code` + 消息里数字抹成 `#`。两个字符都不能省：
  * 抹掉 code，新欠会和不存在的断言混成同一格；
  * 不抹数字，行号与计数每次改文件都漂，账本第二天就全是「新欠」，于是没人再看它。

零基线：没有账本文件就是没有老账，本 scope 静默通过。首版账本必须为空——不许把
bootstrap 当天的 ERROR 整表灌进来，那不是记账，是开张即免罪。

顺序：本 scope 必须最后跑（`verify.py` 的 SCOPES 末尾）。它读的是其它 scope 已经报出来
的 findings，跑早了等于拿半个清单对账。
"""

import datetime
import json
import re
import subprocess
from pathlib import Path

from .common import add, as_dict

NAME = "baseline"
BASELINE_REL = ".harness/baseline.txt"
ACCEPTED_REL = ".harness/accepted.json"
DIGITS = re.compile(r"\d+")
ACCEPTED_FIELDS = ("scope", "path", "fingerprint", "count", "reason", "owner", "review_by")
REVIEW_BY = "%Y-%m-%d"


def fingerprint(code, message):
    return f"{code}:{DIGITS.sub('#', message or '')}"


def key_of(finding):
    return (finding.scope, finding.path or "", fingerprint(finding.code, finding.message))


def _positive_int(raw):
    """条数只接受正整数：0 或 "1 " 这类写法会让「有没有这条账」变成猜谜。"""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, str):
        # 不用 str.isdigit() 把关：它对 "²" 也返回 True，而 int("²") 会抛。
        # 判据只认「int() 能解析且为正」，一条路径，没有第二种解释。
        try:
            value = int(raw.strip())
        except ValueError:
            return None
        return value if value > 0 else None
    return None


def read_baseline(root, findings):
    """返回 {(scope, path, 指纹): 条数}。格式坏的行逐行报 BASE011，不静默跳过。"""
    path = root / BASELINE_REL
    if not path.is_file():
        return {}
    table, bad = {}, []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("\t")]
        count = _positive_int(parts[3]) if len(parts) == 4 else None
        if count is None or not all(parts[:3]):
            bad.append(lineno)
            continue
        key = (parts[0], parts[1], parts[2])
        table[key] = table.get(key, 0) + count
    if bad:
        add(
            findings,
            "ERROR",
            NAME,
            BASELINE_REL,
            bad[0],
            "BASE011",
            f"第 {bad} 行不是「域<TAB>路径<TAB>指纹<TAB>条数」四列且条数为正整数。"
            "账本读不动就不能当通过：跳过坏行等于把它们从账上抹掉",
        )
    return table


def read_accepted(root, findings):
    """返回 {(scope, path, 指纹): 条数}；字段缺失报 BASE011，过期报 BASE012。"""
    path = root / ACCEPTED_REL
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        add(
            findings,
            "ERROR",
            NAME,
            ACCEPTED_REL,
            1,
            "BASE011",
            f"读不了或不是 JSON（{exc}）：豁免表读不动，等于所有豁免都失效",
        )
        return {}
    if not isinstance(data, list):
        add(
            findings,
            "ERROR",
            NAME,
            ACCEPTED_REL,
            1,
            "BASE011",
            "accepted.json 必须是条目数组：一条一个豁免，每条带理由与复查日期",
        )
        return {}
    table, today = {}, datetime.date.today()
    for idx, entry in enumerate(data, 1):
        item = as_dict(entry)
        missing = [f for f in ACCEPTED_FIELDS if not str(item.get(f, "")).strip()]
        count = _positive_int(item.get("count"))
        if missing or count is None:
            lack = missing + ([] if count is not None else ["count(正整数)"])
            add(
                findings,
                "ERROR",
                NAME,
                ACCEPTED_REL,
                idx,
                "BASE011",
                f"第 {idx} 条缺 {', '.join(lack)}。不修就必须盖章，盖章就必须有人"
                "和日期——否则「豁免」只是一句没人负责的注释",
            )
            continue
        try:
            review_by = datetime.datetime.strptime(str(item["review_by"]), REVIEW_BY).date()
        except ValueError:
            add(
                findings,
                "ERROR",
                NAME,
                ACCEPTED_REL,
                idx,
                "BASE011",
                f"第 {idx} 条 review_by = {item.get('review_by')!r} 不是 YYYY-MM-DD",
            )
            continue
        if review_by < today:
            add(
                findings,
                "ERROR",
                NAME,
                ACCEPTED_REL,
                idx,
                "BASE012",
                f"第 {idx} 条豁免已于 {review_by} 过期（{item.get('reason', '')}）。"
                "过期豁免必须重新盖章：换日期、换理由，或删行",
            )
            continue
        key = (str(item["scope"]), str(item["path"]), str(item["fingerprint"]))
        table[key] = table.get(key, 0) + count
    return table


def head_total(root):
    """HEAD 里账本的总条数；不是 git 仓库或 HEAD 没有账本时返回 None。"""
    total = 0
    for rel in (BASELINE_REL, ACCEPTED_REL):
        proc = subprocess.run(
            ["git", "-C", str(root), "show", f"HEAD:{rel}"], check=False, capture_output=True, text=True
        )
        if proc.returncode != 0:
            continue
        if rel == BASELINE_REL:
            for line in proc.stdout.splitlines():
                parts = [p.strip() for p in line.strip().split("\t")]
                if len(parts) == 4 and line.strip() and not line.strip().startswith("#"):
                    total += _positive_int(parts[3]) or 0
        else:
            try:
                entries = json.loads(proc.stdout)
            except json.JSONDecodeError:
                continue
            for entry in entries if isinstance(entries, list) else []:
                total += _positive_int(as_dict(entry).get("count")) or 0
    return total if total else None


def check_monotonic(root, ledger_total, findings):
    """只减不增：刷新账本时总数不许上升。没有 git 就明说判不了，不冒充通过。"""
    previous = head_total(root)
    if previous is None:
        add(
            findings,
            "WARN",
            NAME,
            BASELINE_REL,
            1,
            "BASE013",
            "没有版本控制里的旧账本可比，本次无法判断总数是否上升。「判不了」按 WARN 报出来，不按通过处理",
        )
        return
    if ledger_total > previous:
        add(
            findings,
            "ERROR",
            NAME,
            BASELINE_REL,
            1,
            "BASE013",
            f"账本总数从 {previous} 涨到 {ledger_total}：那不是豁免，是把新欠盖了章。"
            "只减不增——要新增一条 accepted，先修掉一条老账",
        )


def run(ctx, findings):
    root = Path(ctx["root"])
    ledger = read_baseline(root, findings)
    exempt = read_accepted(root, findings)
    if not ledger and not exempt:
        return  # 零基线：没有账，就没有要核的
    allowed = dict(ledger)
    for key, count in exempt.items():
        allowed[key] = allowed.get(key, 0) + count

    current = {}
    for finding in findings:
        if finding.scope != NAME and finding.severity == "ERROR":
            current[key_of(finding)] = current.get(key_of(finding), 0) + 1
    for finding in findings:
        if finding.scope == NAME or finding.severity != "ERROR":
            continue
        key = key_of(finding)
        if current.get(key, 0) <= allowed.get(key, 0):
            finding.severity = "WARN"
            finding.message = f"基线内（账本 {allowed[key]} 条）：{finding.message}"
        else:
            finding.message = f"新欠（账本 {allowed.get(key, 0)} 条）：{finding.message}"

    check_monotonic(root, sum(ledger.values()) + sum(exempt.values()), findings)
    debt = sum(ledger.values()) + sum(exempt.values()) - sum(current.values())
    if debt > 0:
        add(
            findings,
            "WARN",
            NAME,
            BASELINE_REL,
            1,
            "BASE014",
            f"账本比现状多 {debt} 条：老账已修掉一部分，可以刷新账本。"
            "刷新前先确认当前 ERROR 全是同一批老账，并把前后条数记入 memory/decisions.md",
        )
