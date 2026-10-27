#!/usr/bin/env python3
"""证据链行为测试：把 go-dev 拷进临时仓库，跑 make evidence，再 verify。

为什么需要它：`tests/reverse.py` 只验「证据写错时会报」，不验「真实命令能产出证据」。
没有这一层，`make evidence` 可以长期坏着，而所有反向测试照样绿。

需要 Go 与 golangci-lint；不在 `make check` 里（那条必须零 Go 依赖），
由 `make check-evidence` 与 CI 的 sample job 跑。工具缺失时报环境错误，不静默跳过。

用法: python3 tests/evidence_boot.py
退出码: 0 = 通过；1 = 证据链有问题；2 = 环境错误（缺 git / go / golangci-lint）
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates/go-dev-harness"
GIT_ID = ("-c", "user.name=evidence", "-c", "user.email=evidence@example.invalid")


def run(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False, env=env)


def git(root, *args):
    return run(["git", *GIT_ID, *args], root)


def main():
    with tempfile.TemporaryDirectory(prefix="evidence-boot-") as tmp:
        root = Path(tmp) / "repo"
        shutil.copytree(TEMPLATE, root, ignore=shutil.ignore_patterns("__pycache__", ".ruff_cache"))

        config_path = root / ".harness/config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["example"] = False
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        for args in (("init", "-q", "-b", "main"), ("add", "-A"), ("commit", "-q", "-m", "base")):
            proc = git(root, *args)
            if proc.returncode != 0:
                print(f"环境错误: git {' '.join(args)} 失败\n{proc.stderr}", file=sys.stderr)
                return 2

        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        proc = run([sys.executable, str(root / ".harness/scripts/evidence.py"), "--root", str(root)], root, env)
        if proc.returncode != 0:
            print("FAIL evidence.py 没有成功产出证据", file=sys.stderr)
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return 2 if proc.returncode == 2 else 1

        head = git(root, "rev-parse", "HEAD").stdout.strip()
        impl = json.loads((root / ".harness/deliverables/artifacts/impl.json").read_text(encoding="utf-8"))
        test = json.loads((root / ".harness/deliverables/artifacts/test.json").read_text(encoding="utf-8"))
        coverage = test.get("coverage") or {}
        checks = [
            ("impl 仍带 example", impl.get("example") is None),
            ("test 仍带 example", test.get("example") is None),
            ("impl commit 不是 HEAD", impl.get("commit") == head),
            ("test commit 不是 HEAD", test.get("commit") == head),
            ("证据缺 at", bool(impl.get("at")) and bool(test.get("at"))),
            ("build/vet/lint 不是 pass",
             impl.get("build") == impl.get("vet") == impl.get("lint") == "pass"),
            ("race 不是 pass", test.get("race") == "pass"),
            ("coverage 不是数字", isinstance(coverage.get("total"), (int, float))),
            ("benchmarks 为空", bool(test.get("benchmarks"))),
        ]
        bad = [name for name, ok in checks if not ok]
        if bad:
            print("FAIL " + "；".join(bad), file=sys.stderr)
            return 1

        proc = run([sys.executable, str(root / ".harness/scripts/verify.py"), "--root", str(root)], root, env)
        if proc.returncode != 0:
            print("FAIL evidence 之后 verify 仍有 ERROR", file=sys.stderr)
            print(proc.stdout, file=sys.stderr)
            return 1

        print(
            f"PASS evidence: case {test.get('cases')}，"
            f"coverage {coverage.get('total')}% / core {coverage.get('core')}%，"
            f"{len(test.get('benchmarks') or [])} 个 benchmark"
        )
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError as exc:
        print(f"环境错误: {exc}", file=sys.stderr)
        sys.exit(2)
