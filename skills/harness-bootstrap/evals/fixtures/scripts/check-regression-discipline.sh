#!/usr/bin/env bash
# 三段纪律判分器：改前基准 / 改中分步 / 改后回归 + 规则强度已同步到断言。
# 契约：cwd = case workspace 根；exit 0 = pass。
set -uo pipefail

fail=0
bad() { echo "FAIL: $*"; fail=1; }
ok() { echo "OK: $*"; }

# 1. 改后状态：统一入口必须变绿（fixture 改前是 1 ERROR / exit 1）
if [ -f Makefile ]; then
  out=$(make check 2>&1); rc=$?
  echo "--- make check (exit=$rc) ---"; echo "$out" | tail -8
  [ "$rc" -eq 0 ] || bad "改后 make check 仍非 0（回归未通过）"
  echo "$out" | grep -q "WARN" || bad "改后未见 WARN：规则只是被删掉而不是降级，强度未被真正同步"
else
  bad "缺少 Makefile"
fi

# 2. 规则措辞已从「必须」降级
if grep -qE '必须带日期前缀' AGENTS.md 2>/dev/null; then
  bad "AGENTS.md 仍写「必须」，入口与断言不一致"
else
  ok "AGENTS.md 规则措辞已降级"
fi
grep -Eqi '建议|可选|WARN|不强制' AGENTS.md || bad "AGENTS.md 未表达降级后的强度"

# 3. 三段留痕：最终消息里能看出基准、分步、回归三件事（中英表述都认）
m="${EVAL_FINAL_MESSAGE:-}"
[ -n "$m" ] || bad "缺少 final message，无法核对纪律留痕"
grep -Eqi '改前|改动前|基线|基准|before|baseline' <<<"$m" || bad "最终消息未交代改前基准"
grep -Eqi '改后|回归|对照|after|regression|verify' <<<"$m" || bad "最终消息未交代改后回归"

# 4. 反向验证或三边对账至少其一被交代
grep -Eqi '反向|三边|对账|违规样本|reverse|self-test|negative|injected' <<<"$m" || bad "未交代反向验证/三边对账"

exit $fail
