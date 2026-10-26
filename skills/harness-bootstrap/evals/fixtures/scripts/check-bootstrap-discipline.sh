#!/usr/bin/env bash
# bootstrap 纪律判分器：五阶段留痕 + 基线/决策留痕 + 规则-断言配对。
# 契约：cwd = case workspace 根；exit 0 = pass。
# 判据同时接受中文与英文表述：被测模型的汇报语言不受控，判据不该绑死语言。
set -uo pipefail

fail=0
bad() { echo "FAIL: $*"; fail=1; }
ok() { echo "OK: $*"; }
m="${EVAL_FINAL_MESSAGE:-}"
[ -n "$m" ] || { echo "FAIL: 缺少 final message"; exit 1; }

# 1. 阶段 0 盘点：说过规模或立过基线
grep -Eqi '盘点|基线|规模|baseline|inventory|survey|dirs|文件数' <<<"$m" || bad "最终消息未交代盘点（阶段 0）"

# 2. 阶段 1 契约：决策留痕
dec=$(find .harness -maxdepth 3 -type f -name 'decisions.md' | head -1)
if [ -n "$dec" ]; then
  ok "decisions.md 存在"
  grep -Eqi '否掉|否决|理由|替代|rejected|alternative|reason' "$dec" || bad "decisions.md 未记录被否方案或理由"
else
  bad "缺少 decisions.md：契约决策未留痕"
fi

# 3. 阶段 3 断言：基线或明确的空账声明
if find .harness -maxdepth 3 -type f \( -name 'baseline*' -o -name '*baseline*.csv' \) | grep -q .; then
  ok "baseline 存在"
else
  grep -Eqi '基线|0 ERROR|无存量|baseline|zero debt' <<<"$m" || bad "既无 baseline 也未声明基线状态"
fi

# 4. 阶段 4/5 流程与状态
[ -f .harness/workflow/flow.json ] || bad "缺少 .harness/workflow/flow.json（流程层）"
find .harness/deliverables .harness/tasks .harness/memory -maxdepth 2 -type f 2>/dev/null | grep -q . \
  || bad ".harness 状态层为空（deliverables/tasks/memory 都没有产物）"

# 5. 反向测试被交代（断言设计纪律）
grep -Eqi '反向|违规样本|反向测试|reverse|self-test|selftest|negative test|injected' <<<"$m" || bad "未交代断言的反向测试"

exit $fail
