"""gates: 入口形状 + 流程契约（workflow/*.json）+ 门记录 + 账本 + 状态层。

阶段不再写死在本文件里：`workflow/flow.json` 是唯一事实源，
`transitions.json` 定义结果状态机，`contract.json` 定义门记录必填字段与账本位置。
"""
import json
import re
from pathlib import Path

from .common import (
    add,
    as_dict,
    as_list,
    build_guide,
    check_fields,
    check_lessons,
    load_json,
    parse_date,
    text,
    validate_change,
    validate_exception,
    warn_example,
)

NAME = "gates"
HARNESS = ".harness"
FLOW = f"{HARNESS}/workflow/flow.json"
TRANSITIONS = f"{HARNESS}/workflow/transitions.json"
CONTRACT = f"{HARNESS}/workflow/contract.json"
BOARD = f"{HARNESS}/tasks/board.json"
LESSONS = f"{HARNESS}/memory/lessons.md"
GUIDE = f"{HARNESS}/codebase-guide/index.json"
TASK_STATUS = ("todo", "doing", "blocked", "done")
AGENTS_MAX_LINES = 150


def run(ctx, findings):
    root = Path(ctx["root"])
    flow = load_json(root, FLOW, NAME, findings, "GATE001")
    transitions = load_json(root, TRANSITIONS, NAME, findings, "GATE001")
    contract = load_json(root, CONTRACT, NAME, findings, "GATE001")
    if not isinstance(flow, dict) or not isinstance(transitions, dict) or not isinstance(contract, dict):
        return

    stages = check_flow(flow, findings)
    if not stages:
        return
    check_agents(root, stages, findings)

    version = flow.get("version")
    gate_fields = [f for f in as_list(contract.get("gate_fields")) if isinstance(f, str)]
    if not gate_fields:
        add(findings, "ERROR", NAME, CONTRACT, 1, "GATE001", "contract.json 缺 gate_fields")

    records = {}
    for stage in stages:
        rel = f"{HARNESS}/deliverables/gates/{stage['gate']}"
        data = load_json(root, rel, NAME, findings, "GATE001")
        if data is None:
            continue
        warn_example(data, rel, NAME, findings, ctx["strict"])
        records[stage["id"]] = data
        check_gate(data, rel, stage, version, gate_fields, transitions, findings)
        check_deliverable(root, stage, findings)

    check_order(stages, records, transitions, findings)
    check_ledgers(root, contract, findings)
    check_state(root, [s["id"] for s in stages], findings)


def check_flow(flow, findings):
    version = flow.get("version")
    if not text(version):
        add(findings, "ERROR", NAME, FLOW, 1, "GATE001", "flow.json 缺 version")
    stages = [s for s in as_list(flow.get("stages")) if isinstance(s, dict)]
    if not stages:
        add(findings, "ERROR", NAME, FLOW, 1, "GATE001", "flow.json 的 stages 为空")
        return []
    seen_ids, seen_gates = set(), set()
    for stage in stages:
        check_fields(stage, ("id", "order", "name", "gate", "deliverable", "scopes"),
                     NAME, FLOW, findings, "GATE001", "stage.")
        sid = stage.get("id")
        if sid in seen_ids:
            add(findings, "ERROR", NAME, FLOW, 1, "GATE001", f"stage id 重复: {sid!r}")
        seen_ids.add(sid)
        if stage.get("gate") in seen_gates:
            add(findings, "ERROR", NAME, FLOW, 1, "GATE001", f"gate 文件重复: {stage.get('gate')!r}")
        seen_gates.add(stage.get("gate"))
    orders = sorted(s.get("order") for s in stages if isinstance(s.get("order"), int))
    if orders != list(range(1, len(stages) + 1)):
        add(findings, "ERROR", NAME, FLOW, 1, "GATE001",
            f"stage.order 必须是 1..{len(stages)} 的连续整数，实际 {orders}")
    return sorted(stages, key=lambda s: s.get("order", 0))


def check_agents(root, stages, findings):
    path = root / "AGENTS.md"
    rel = "AGENTS.md"
    if not path.is_file():
        add(findings, "ERROR", NAME, rel, 1, "GATE002", "缺少 AGENTS.md")
        return
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if len(lines) > AGENTS_MAX_LINES:
        add(findings, "ERROR", NAME, rel, 1, "GATE002",
            f"AGENTS.md 超过 {AGENTS_MAX_LINES} 行（{len(lines)}）")
    for token in ("<!-- agents: scope=. parent= -->", "阶段路由", "scope=", "make check", "人判项"):
        if token not in content:
            add(findings, "ERROR", NAME, rel, 1, "GATE002", f"AGENTS.md 缺少 {token!r}")
    scope_tokens = ["gates"]
    for stage in stages:
        for scope in as_list(stage.get("scopes")):
            if scope not in scope_tokens:
                scope_tokens.append(scope)
    for scope in scope_tokens:
        if f"scope={scope}" not in content:
            add(findings, "ERROR", NAME, rel, 1, "GATE002", f"AGENTS.md 未路由 scope={scope}")
    for required in (
        FLOW,
        f"{HARNESS}/workflow/README.md",
        f"{HARNESS}/scripts/verify.py",
        f"{HARNESS}/config.json",
    ):
        if not (root / required).is_file():
            add(findings, "ERROR", NAME, rel, 1, "GATE002", f"目录地图指向的 {required} 不存在")
    for idx, line in enumerate(lines, 1):
        for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", line):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            rel_target = target.split("#", 1)[0].split("?", 1)[0]
            if rel_target and not (root / rel_target).exists():
                add(findings, "ERROR", NAME, rel, idx, "GATE002",
                    f"AGENTS.md 相对链接指向不存在的文件: {target}")


def check_gate(data, rel, stage, version, gate_fields, transitions, findings):
    check_fields(data, tuple(gate_fields), NAME, rel, findings, "GATE003")
    if data.get("stage") != stage["id"]:
        add(findings, "ERROR", NAME, rel, 1, "GATE003",
            f"stage 应为 {stage['id']!r}，实际 {data.get('stage')!r}")
    if data.get("process_version") != version:
        add(findings, "ERROR", NAME, rel, 1, "GATE003",
            f"process_version 与 workflow/flow.json 不一致（{data.get('process_version')!r} != {version!r}）")
    if parse_date(data.get("date")) is None:
        add(findings, "ERROR", NAME, rel, 1, "GATE003", "date 不是 YYYY-MM-DD")
    result = data.get("result")
    allowed = [r for r in as_list(transitions.get("results")) if isinstance(r, str)]
    if result not in allowed:
        add(findings, "ERROR", NAME, rel, 1, "GATE003",
            f"result 必须是 {allowed}，实际 {result!r}")
        return
    requires = as_dict(transitions.get("requires")).get(result) or []
    for key in requires:
        if not as_list(data.get(key)):
            add(findings, "ERROR", NAME, rel, 1, "GATE003", f"{result} 必须有 {key}")
    for exc in as_list(data.get("exceptions")):
        if not isinstance(exc, dict):
            add(findings, "ERROR", NAME, rel, 1, "GATE004", "exceptions 的条目必须是对象")
            continue
        validate_exception(exc, NAME, rel, findings, "GATE004")


def check_deliverable(root, stage, findings):
    rel = f"{HARNESS}/deliverables/{stage['deliverable']}"
    if not (root / rel).is_file():
        add(findings, "ERROR", NAME, rel, 1, "GATE006",
            f"阶段 {stage['id']} 声明了交付物 {stage['deliverable']}，但文件不存在")


def check_order(stages, records, transitions, findings):
    blocking = [r for r in as_list(transitions.get("blocking")) if isinstance(r, str)]
    blocked = False
    for stage in stages:
        data = records.get(stage["id"])
        if data is None:
            blocked = True
            continue
        result = data.get("result")
        if blocked and result not in blocking:
            add(findings, "ERROR", NAME, f"{HARNESS}/deliverables/gates/{stage['gate']}", 1, "GATE004",
                f"前序阶段未通过，{stage['id']} 不能为 {result}")
        if result in blocking:
            blocked = True


def check_ledgers(root, contract, findings):
    ledgers = as_dict(contract.get("ledgers"))
    changes_rel = f"{HARNESS}/{ledgers.get('changes', 'deliverables/ledgers/changes.json')}"
    exceptions_rel = f"{HARNESS}/{ledgers.get('exceptions', 'deliverables/ledgers/exceptions.json')}"
    changes = load_json(root, changes_rel, NAME, findings, "GATE005")
    if isinstance(changes, list):
        seen = set()
        for change in changes:
            if not isinstance(change, dict):
                add(findings, "ERROR", NAME, changes_rel, 1, "GATE005", "change 条目必须是对象")
                continue
            cid = change.get("id")
            if cid in seen:
                add(findings, "ERROR", NAME, changes_rel, 1, "GATE005", f"change id 重复: {cid!r}")
            seen.add(cid)
            validate_change(change, NAME, changes_rel, findings, "GATE005")
            if change.get("type") == "contract" and len(as_list(change.get("notified"))) < 2:
                add(findings, "ERROR", NAME, changes_rel, 1, "GATE005",
                    f"change {cid!r} 是契约变更，notified 至少要有上下游两方")
    elif changes is not None:
        add(findings, "ERROR", NAME, changes_rel, 1, "GATE005", "changes.json 必须是数组")

    exceptions = load_json(root, exceptions_rel, NAME, findings, "GATE005")
    if isinstance(exceptions, list):
        seen = set()
        for exc in exceptions:
            if not isinstance(exc, dict):
                add(findings, "ERROR", NAME, exceptions_rel, 1, "GATE005", "exception 条目必须是对象")
                continue
            eid = exc.get("id")
            if eid in seen:
                add(findings, "ERROR", NAME, exceptions_rel, 1, "GATE005", f"exception id 重复: {eid!r}")
            seen.add(eid)
            validate_exception(exc, NAME, exceptions_rel, findings, "GATE005")
    elif exceptions is not None:
        add(findings, "ERROR", NAME, exceptions_rel, 1, "GATE005", "exceptions.json 必须是数组")


def check_state(root, stage_ids, findings):
    board = load_json(root, BOARD, NAME, findings, "GATE007")
    if isinstance(board, dict):
        tasks = as_list(board.get("tasks"))
        if not tasks:
            add(findings, "ERROR", NAME, BOARD, 1, "GATE007", "tasks 为空：看板至少要有在做的任务")
        seen = set()
        for task in tasks:
            if not isinstance(task, dict):
                add(findings, "ERROR", NAME, BOARD, 1, "GATE007", "task 条目必须是对象")
                continue
            check_fields(task, ("id", "title", "owner", "stage", "status", "updated"),
                         NAME, BOARD, findings, "GATE007", "task.")
            tid = task.get("id")
            if tid in seen:
                add(findings, "ERROR", NAME, BOARD, 1, "GATE007", f"task id 重复: {tid!r}")
            seen.add(tid)
            if task.get("stage") not in stage_ids:
                add(findings, "ERROR", NAME, BOARD, 1, "GATE007",
                    f"task {tid!r} 的 stage {task.get('stage')!r} 不在 flow.json 里")
            if task.get("status") not in TASK_STATUS:
                add(findings, "ERROR", NAME, BOARD, 1, "GATE007",
                    f"task {tid!r} 的 status 必须是 {list(TASK_STATUS)}")
            if parse_date(task.get("updated")) is None:
                add(findings, "ERROR", NAME, BOARD, 1, "GATE007", f"task {tid!r} 的 updated 不是 YYYY-MM-DD")

    lessons = root / LESSONS
    if not lessons.is_file():
        add(findings, "ERROR", NAME, LESSONS, 1, "GATE007", "缺 memory/lessons.md")
    else:
        check_lessons(lessons.read_text(encoding="utf-8"), NAME, LESSONS, findings, "GATE007")

    guide_path = root / GUIDE
    if not guide_path.is_file():
        add(findings, "ERROR", NAME, GUIDE, 1, "GUIDE001",
            "缺 codebase-guide/index.json；跑 python3 .harness/scripts/gen_guide.py 生成")
        return
    try:
        current = json.loads(guide_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        add(findings, "ERROR", NAME, GUIDE, 1, "GUIDE001", f"index.json 解析失败: {exc}")
        return
    if current != build_guide(root):
        add(findings, "ERROR", NAME, GUIDE, 1, "GUIDE001",
            "索引与磁盘不一致（人手改过或忘了重新生成）：跑 gen_guide.py")
