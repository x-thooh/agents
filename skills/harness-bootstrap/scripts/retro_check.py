"""retro_check：复盘写得合不合规——三栏都要可核验。

为什么与 `retro.py` 分开：那边是**事实底板**（先把本轮的 audit / fixtures / round 数字算出来），
这边是**校验器**（复盘正文有没有挂在这些数字上）。底板坏了是什么都算不出，校验器坏了是
算得出却判不了——混在一个文件里，前者会掩护后者。表与证据那一半在 `retro_board.py`。

`拦到 0` 的复检结论是这里唯一「机制自己判自己」的地方：一条规则整轮没拦到任何东西，要么
说清为什么还值得留，要么这轮就削它。缺这一栏，「0 次」与「一直在有效工作」在账面上长得
一模一样，而两者要做的动作相反。数字本身由 `retro.py` 算，这里不重算。

用法: python3 scripts/retro_check.py
退出码: 0 = 通过 / 判不了；1 = 复盘不合规；2 = 环境错误
"""

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import retro_board  # noqa: E402  （先修 sys.path：脚本可被拷到别处跑）

SKILL = HERE.parent
ROOT = SKILL.parents[1]

REQUIRED = ("拦到：", "工单：")
REVIEW = "复检："
DECISIONS = ("保留", "简化", "删除", "降级")
REVIEW_MIN = 6
CODE = re.compile(r"\b[A-Z]{2,}[0-9]{3}\b")


def _review(text):
    """返回复检结论：None = 没有这一栏，"" = 有但不合格，否则返回结论词。

    为什么要求「结论词 + 理由」两段：只写「保留」是一个人就能盖的章；只写形容词
    （「仍然必要」）则区分不出「保留」与「削掉」。结论词落在闭集里由机器判，理由留在
    正文里由人看——机器判不了「为什么还值得留」，但可以判「有没有说」。
    """
    if REVIEW not in text:
        return None
    body = text.split(REVIEW, 1)[1].split("\n", 1)[0].strip()
    verb = next((d for d in DECISIONS if d in body), None)
    if verb is None:
        return ""
    rest = body.replace(verb, "", 1).strip(" ：:,，。、\t")
    return verb if len(rest) >= REVIEW_MIN else ""


def _columns(path, text, board, bad, cited):
    """文字侧的发现：三栏在不在、拦到栏是 code 还是 0、拦到 0 时的复检结论。"""
    lack = [k for k in REQUIRED if k not in text]
    if lack:
        bad.append(f"{path.name}: 缺 {' '.join(k.rstrip('：') for k in lack)}")
        return
    hit = text.split(REQUIRED[0], 1)[1].split("\n", 1)[0].strip()
    if hit != "0":
        if not CODE.search(hit):
            bad.append(f"{path.name}: 拦到一栏既不是 0，也没点名任何 code——那是感想不是台账")
    else:
        got = _review(text)
        if got is None:
            bad.append(
                f"{path.name}: 拦到 0 却没有「{REVIEW}」行——没拦到的一轮必须说清是保留还是"
                "削掉。沉默的机制与有效的机制在账面上长得一样，而两者要做的动作相反"
            )
        elif not got:
            bad.append(
                f"{path.name}: 复检行要给结论（{'/'.join(DECISIONS)} 之一）再加至少 "
                f"{REVIEW_MIN} 个字的理由——「保留。」是一个人就能盖的章，不是判据"
            )
    ids = re.findall(r"\bR-\d+\b", text.split(REQUIRED[1], 1)[1].split("\n", 1)[0])
    if not ids:
        bad.append(f"{path.name}: 工单栏没有指向任何 R-N——「无」不是默认值，要写就必须给理由")
        return
    for tid in ids:
        cited.add(tid)
        if tid not in board:
            bad.append(f"{path.name}: 工单 {tid} 不在 tasks.json 里")


def check(root=None):
    """三栏都必须可核验：拦到点名 code 或写 0 并给复检结论、工单指向表里有的 id、
    完成态带证据。"""
    root = pathlib.Path(root or ROOT)
    retro = root / "archive" / "retro"
    files = sorted(retro.glob("*.md")) if retro.is_dir() else []
    if not files:
        print(f"retro: {retro} 下还没有复盘——判不了，不冒充通过")
        return 0
    board = retro_board.load(retro)
    if not board:  # None = 没建表；False = 坏 JSON。两种都判不了，不冒充通过
        print(f"retro: {retro}/tasks.json 缺失或不是合法 JSON——工单栏无从核验", file=sys.stderr)
        return 2
    bad, cited = [], set()
    for path in files:
        _columns(path, path.read_text(encoding="utf-8"), board, bad, cited)
    board_bad, undecided = retro_board.findings(root, board, cited)
    bad += board_bad
    if bad:
        for line in bad:
            print(f"FAIL {line}", file=sys.stderr)
        return 1
    if undecided:
        # 退出码 2 = 判不了。与 1（不合规）分开：这条链上「历史不全」与「工单说谎」
        # 的动作相反，用同一个码会让人去改没错的那一边。
        for line in undecided:
            print(f"UNDECIDED {line}", file=sys.stderr)
        return 2
    print(f"retro: {len(files)} 篇复盘通过；工单 {len(cited)} 条全部可追溯")
    return 0


if __name__ == "__main__":
    sys.exit(check())
