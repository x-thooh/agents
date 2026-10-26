"""conf: .harness/config.json 自身的诚实性——键名拼写与示例标记。

  CONF001    键名拼错 / 未知键 → ERROR（静默忽略未知键 = 整条扫描被关掉）
  EXAMPLE001 config.json 自己是示例数据（复用 common.warn_example）
"""
from .common import add, warn_example

NAME = "conf"

# 键名闭集：枚举值一律常量表（§二.2）。值 None = 标量；值 set = 该键下允许的子键。
ALLOWED = {
    "example": None,
    "task_max_days": None,
    "coverage": {"core_min", "noncore_min", "new_code_min"},
    "review_max_lines": None,
    "reviewers": {"default", "core"},
    "selftest_pass_rate": None,
    "smoke_pass_rate": None,
    "doc_lead_business_days": None,
    "re_review_business_days": None,
}

REL = ".harness/config.json"


def _unknown(findings, key, allowed_hint):
    add(findings, "ERROR", NAME, REL, 1, "CONF001",
        f"未知配置键 {key!r}：verify 会静默忽略它——一整条扫描就此被关掉。"
        f"允许的键：{allowed_hint}。新增配置项要同批更新 conf.py 的 ALLOWED")


def run(ctx, findings):
    quality = ctx.get("quality") or {}
    warn_example(quality, REL, NAME, findings, ctx["strict"])

    for key in sorted(quality):
        spec = ALLOWED.get(key, "unknown")
        if spec == "unknown":
            _unknown(findings, key, ", ".join(sorted(ALLOWED)))
            continue
        if isinstance(spec, set) and isinstance(quality.get(key), dict):
            for sub in sorted(quality[key]):
                if sub not in spec:
                    _unknown(findings, f"{key}.{sub}", ", ".join(sorted(spec)))
