#!/usr/bin/env python3
"""生成 references/code-index.md —— 全部 code 的清单，只准脚本写。

为什么生成器独立在这里，而不是塞进 audit.py：
`audit.py` 的契约是「只读，不写文件」。让门禁顺手写盘，等于让它自己改证据；
而「派生数据要不要重生成」是人的动作，不是判定的副产品。

用法:
  python3 scripts/gen_code_index.py        # 重写 references/code-index.md
  make code-index                          # 同上，走统一入口

生成后 audit.py 的 codeindex scope 会重新生成一遍做逐字节比对，
不一致即 ERROR —— 手改这个文件一定被拦。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from scopes import codeindex  # noqa: E402  （必须先修好 sys.path 再导入）


def main():
    skill_dir = os.path.dirname(_HERE)
    target = os.path.join(skill_dir, codeindex.INDEX_REL)
    scopes_dir = os.path.join(skill_dir, codeindex.SCOPES_REL)
    text, unreadable = codeindex.render(scopes_dir)
    if unreadable:
        print("生成中止：有 scope 模块读不动，清单会不完整 —— " + "；".join(unreadable),
              file=sys.stderr)
        return 1
    try:
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as exc:
        print(f"写不了 {target}: {exc}", file=sys.stderr)
        return 2
    print(f"已重写 {codeindex.INDEX_REL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
