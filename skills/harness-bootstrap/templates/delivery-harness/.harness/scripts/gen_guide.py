#!/usr/bin/env python3
"""生成 codebase-guide/index.json。

索引是派生数据：只准脚本写，人手改一个字都会被 gates scope 判 ERROR
（重新生成后逐字节比对）。用法：python3 .harness/scripts/gen_guide.py [仓库根]
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from scopes.common import build_guide  # noqa: E402


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(argv[0]).resolve() if argv else HERE.parents[1]
    target = root / ".harness/codebase-guide/index.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_guide(root), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
