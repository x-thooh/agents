#!/usr/bin/env python3
"""模板装上之后是否仍然诚实 —— 这是唯一一条验「行为」的门禁。

为什么需要它：本仓库其余 43 个 fixture 全是文本形状的反向样本（少一段、多一个 code），
没有一个验「把模板拷进真仓库后它说什么」。`check-templates` 跑的是模板在**自己目录里**
的自洽性，那是自证。于是这套东西历史上第一次面对非自身输入时，一次就撞出假绿灯：

  把 deliverables 的 example 去掉（模拟「换成真数据」）、config.json 没动，
  `verify --strict` 报 0 ERROR 0 WARN —— 而仓库里的库代码 panic 一次也没被检查到，
  因为 go_src 还指着模板自带的 sample/。

三条断言：
  ① 原样拷入 → verify 退出码 0（模板必须自带一个绿的起点）
  ② 原样拷入 → verify --strict 退出码 1（示例数据必须被拦，否则 strict 是装饰）
  ③ go-dev：去掉 deliverables 的 example、config 不动 → strict 仍退出码 1
     且必须报 CONF002（还在扫 sample）。这条就是上面那次事故的回归测试。

用法: python3 tests/template_boot.py
退出码: 0 = 全过；1 = 有失败；2 = 环境错误
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ("go-dev-harness", "delivery-harness")
BRIDGE = "go-dev-harness"  # 唯一带 go_src 的模板，③ 只对它有意义


def boot(tpl, tmp):
    target = Path(tmp) / tpl
    shutil.copytree(ROOT / "templates" / tpl, target,
                    ignore=shutil.ignore_patterns("__pycache__", ".ruff_cache"))
    return target


def verify(root, strict=False):
    cmd = [sys.executable, str(root / ".harness/scripts/verify.py")]
    if strict:
        cmd.append("--strict")
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def strip_examples(root):
    """把 deliverables 下的 example: true 去掉 —— 模拟「换成真数据」这一步。"""
    n = 0
    for path in (root / ".harness/deliverables").rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        # 有些交付物顶层是数组（账本类），没有 example 键可去 —— 不是缺陷，跳过。
        if not isinstance(data, dict):
            continue
        if data.pop("example", None) is not None:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            n += 1
    return n


def regen_guide(root):
    gen = root / ".harness/scripts/gen_guide.py"
    if gen.is_file():
        subprocess.run([sys.executable, str(gen)], check=False, capture_output=True, text=True)


def main():
    failures = []
    for tpl in TEMPLATES:
        with tempfile.TemporaryDirectory() as tmp:
            root = boot(tpl, tmp)

            code, out = verify(root)
            if code != 0:
                failures.append(f"{tpl}: 原样拷入后 verify 应当退出 0，实际 {code}\n{out[-800:]}")
            else:
                print(f"PASS {tpl}: 原样拷入 verify 退出 0")

            code, out = verify(root, strict=True)
            if code != 1:
                failures.append(f"{tpl}: 原样拷入 --strict 应当退出 1（示例必须被拦），实际 {code}")
            elif not re.search(r"EXAMPLE001", out):
                failures.append(f"{tpl}: --strict 退出 1 但没有 EXAMPLE001 —— 别的错在冒充")
            else:
                print(f"PASS {tpl}: --strict 拦下示例数据")

            if tpl != BRIDGE:
                continue

            removed = strip_examples(root)
            regen_guide(root)
            code, out = verify(root, strict=True)
            if code != 1:
                failures.append(
                    f"{tpl}: 去掉 {removed} 个 example、config 不动时 --strict 必须仍然退出 1，"
                    f"实际 {code} —— 这就是假绿灯（门禁扫着模板自带的 sample/ 却说全绿）")
            elif "CONF002" not in out:
                failures.append(f"{tpl}: 退出 1 但没报 CONF002（go_src 仍指 sample/），信号指错了地方")
            else:
                print(f"PASS {tpl}: 去掉 {removed} 个 example 后仍报 CONF002（还在扫 sample）")

    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        print(f"{len(failures)} 例不符合期望", file=sys.stderr)
        return 1
    print("ALL TEMPLATE BOOT TESTS PASSED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError as exc:
        print(f"环境错误: {exc}", file=sys.stderr)
        sys.exit(2)
