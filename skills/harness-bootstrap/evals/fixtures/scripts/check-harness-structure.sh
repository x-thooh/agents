#!/usr/bin/env bash
# 结构判分器：校验 harness-bootstrap 产出的 .harness/ 十件套。
# 契约：cwd = case workspace 根；exit 0 = pass。
set -uo pipefail

fail=0
note() { echo "$*"; }
bad() { echo "FAIL: $*"; fail=1; }

# 1. 入口
if [ ! -f AGENTS.md ]; then
  bad "AGENTS.md 不存在"
else
  lines=$(wc -l < AGENTS.md | tr -d ' ')
  note "AGENTS.md 行数: $lines"
  if [ "$lines" -gt 150 ]; then bad "AGENTS.md 超过 150 行（$lines），入口应只放指针"; fi
  if ! grep -qE '无断言|断言|scope' AGENTS.md; then
    bad "AGENTS.md 未出现断言/scope 标注，规则与断言未配对"
  fi
fi

# 2. .harness 十件套
for d in .harness .harness/scripts .harness/workflow .harness/specs .harness/deliverables \
         .harness/tasks .harness/memory .harness/codebase-guide .harness/stack-templates .harness/git-hooks; do
  [ -d "$d" ] || bad "$d 目录不存在"
done
[ -f .harness/config.json ] || bad ".harness/config.json 不存在（单一根配置）"
[ -f .harness/workflow/flow.json ] || bad "缺 .harness/workflow/flow.json（阶段唯一事实源）"

# 3. 可执行校验脚本
verify=$(find .harness/scripts -maxdepth 2 -type f \( -name 'verify*.py' -o -name 'verify*.sh' \) 2>/dev/null | head -1)
if [ -z "$verify" ]; then bad "未找到 .harness/scripts 下的 verify 脚本（执行层）"; else note "verify: $verify"; fi

# 4. 统一命令入口（Makefile 或等价）
if [ -f Makefile ]; then
  if [ -n "$verify" ] && ! grep -q "$(basename "$verify")" Makefile; then
    bad "Makefile 未引用 verify 脚本，命令未集中"
  fi
else
  bad "缺少 Makefile（统一命令入口）"
fi

# 5. 状态层至少一份可接续的东西（deliverables / tasks / memory）
found=$(find .harness/deliverables .harness/tasks .harness/memory -maxdepth 2 -type f 2>/dev/null | head -1)
[ -n "$found" ] || bad ".harness 状态层为空（deliverables/tasks/memory 都没有产物）"

# 6. 基线账本（有隐性存量时应留痕；空仓允许无 baseline，但需决策记录）
if ! find .harness -maxdepth 3 -type f \( -name 'baseline*' -o -name 'decisions.md' \) | grep -q .; then
  bad "既无 baseline 也无 decisions.md：缺少基准或决策留痕"
fi

exit $fail
