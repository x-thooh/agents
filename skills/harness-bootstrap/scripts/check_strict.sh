#!/usr/bin/env bash
# 断言模板的 --strict 真的在拦示例数据：期望退出码 1。
#
# 为什么是 1 而不是 0：模板里带 example: true 的示例证据，--strict 必须把它们判成
# ERROR。所以「--strict 通过」反而是坏消息——说明 strict 失效了，或者示例数据被换成
# 真实数据后这句断言该同步改。
#
# 为什么单独一个脚本而不是写在 Makefile 里：Make 要把 $ 写成 $$，而 shellcheck 读的是
# Makefile 原文，于是 `[ $$? -eq 1 ]` 被它当成 PID 拼接，报 SC2255；先接变量又报
# SC2034（「变量没用」）。绕标注不如把判断搬出 Make —— 顺带这段逻辑现在能单独跑。
#
# 用法: check_strict.sh <模板名> <verify.py 路径>
set -u

if [ "$#" -ne 2 ]; then
  echo "用法: $0 <模板名> <verify.py 路径>" >&2
  exit 2
fi

name="$1"
verify="$2"

if [ ! -f "$verify" ]; then
  echo "  $name --strict 判不了：$verify 不存在（路径改了就同步这里）" >&2
  exit 2
fi

python3 "$verify" --strict >/dev/null 2>&1
rc=$?

if [ "$rc" -eq 1 ]; then
  echo "  $name --strict 拦下示例数据（预期）"
  exit 0
fi

echo "  $name --strict 期望退出码 1，实际 $rc：example: true 被改掉，或 strict 失效" >&2
exit 1
