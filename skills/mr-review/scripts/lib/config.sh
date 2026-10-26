#!/usr/bin/env bash
# ============================================================================
# config.sh — 项目 profile 解析（让 mr-review 在任意仓库可用）
#
# mr-review 的脚本本身与仓库无关，仓库差异（服务目录、构建命令、插件模块、
# 测试人员、提测分支…）全部从 profile JSON 读取。没有 profile 也能跑：走内置默认。
#
# profile 查找顺序（先命中先用，结果写进 MRC_PROFILE_FILE）：
#   1. $MR_REVIEW_CONFIG                            显式指定
#   2. <repo>/.mr-review.json                       仓库内（可提交，团队共享 —— 推荐）
#   3. <repo>/.pi/mr-review.json                    仓库内（Pi 配置目录）
#   4. ~/.pi/mr-review/profiles/<repo-name>.json    本机按仓库名
#   5. ~/.pi/mr-review/config.json                  本机全局
#   6. 内置默认（无 profile）
#
# profile 字段见 config/mr-review.example.json；全部可选。
#
# 用法：
#   source scripts/lib/config.sh
#   mrcfg_init [start_dir]      # 设置 MRC_ROOT / MRC_PROFILE_FILE / MRC_MODULE / 分支名
#   mrcfg_services_from_files "<changed files>"     # → 空格分隔服务名
#   mrcfg_build_cmd <svc>       # → 在服务目录内执行的编译命令
#   mrcfg_codegen_cmd           # → 仓库根执行的代码生成命令（空=跳过）
#   mrcfg_test_cmd              # → 测试命令
#   mrcfg_plugin_modules "<changed files>"          # → 空格分隔模块目录（相对根）
#   mrcfg_shared_pkg_impact <pkg>                   # → 引用该共享包的服务
#   mrcfg_tester_mobile / mrcfg_repo_id / mrcfg_dingtalk_keyword / mrcfg_merge_type
#
# 兼容 bash 3.2（macOS 自带），不依赖 mapfile / 关联数组。
# ============================================================================

MRC_ROOT="${MRC_ROOT:-}"
MRC_PROFILE_FILE="${MRC_PROFILE_FILE:-}"
MRC_MODULE="${MRC_MODULE:-}"
MRC_MAIN_BRANCH="${MRC_MAIN_BRANCH:-master}"
MRC_SERVICE_GLOB="${MRC_SERVICE_GLOB:-}"
MRC_PLUGIN_ALL="${MRC_PLUGIN_ALL:-0}"

# 超时执行：优先 timeout / gtimeout，都没有（macOS 默认无 coreutils）时直接执行
mrcfg_timeout() { # <秒> <命令...>
	local secs="$1"
	shift
	if command -v timeout >/dev/null 2>&1; then
		timeout "$secs" "$@"
	elif command -v gtimeout >/dev/null 2>&1; then
		gtimeout "$secs" "$@"
	else
		"$@"
	fi
}

# ------------------------------------------------------------------ 路径解析

# 向上查找仓库根：优先 .git（普通仓库/worktree 均适用），退回 Makefile+go.mod
mrcfg_find_root() {
	local dir="${1:-$PWD}"
	dir="$(cd "$dir" 2>/dev/null && pwd)" || return 1
	local cur="$dir"
	while [ -n "$cur" ]; do
		if [ -e "${cur}/.git" ]; then
			printf '%s' "$cur"
			return 0
		fi
		cur=$(dirname "$cur")
	done
	cur="$dir"
	while [ -n "$cur" ]; do
		if [ -f "${cur}/go.mod" ]; then
			printf '%s' "$cur"
			return 0
		fi
		cur=$(dirname "$cur")
	done
	return 1
}

mrcfg_find_profile() {
	local root="$1"
	local cand
	for cand in \
		"${MR_REVIEW_CONFIG:-}" \
		"${root}/.mr-review.json" \
		"${root}/.pi/mr-review.json" \
		"${HOME}/.pi/mr-review/profiles/$(basename "$root").json" \
		"${HOME}/.pi/mr-review/config.json"; do
		if [ -n "$cand" ] && [ -f "$cand" ]; then
			printf '%s' "$cand"
			return 0
		fi
	done
	if [ -n "${MR_REVIEW_CONFIG:-}" ] && [ ! -f "${MR_REVIEW_CONFIG}" ]; then
		echo "warn: MR_REVIEW_CONFIG 指向的文件不存在: ${MR_REVIEW_CONFIG}（走其余候选/内置默认）" >&2
	fi
	return 0
}

# 读 profile 字段：mrcfg_get <jq 表达式> <默认值>
mrcfg_get() {
	local expr="$1" dflt="${2:-}"
	if [ -z "${MRC_PROFILE_FILE}" ] || [ ! -f "${MRC_PROFILE_FILE}" ]; then
		printf '%s' "$dflt"
		return 0
	fi
	local v
	v=$(jq -r "(${expr}) // empty" "${MRC_PROFILE_FILE}" 2>/dev/null || true)
	if [ -z "$v" ] || [ "$v" = "null" ]; then
		printf '%s' "$dflt"
		return 0
	fi
	printf '%s' "$v"
}

# 读数组字段，逐行输出：mrcfg_get_list '.plugin_dirs'
mrcfg_get_list() {
	local expr="$1"
	[ -n "${MRC_PROFILE_FILE}" ] && [ -f "${MRC_PROFILE_FILE}" ] || return 0
	jq -r "(${expr}) // [] | .[]" "${MRC_PROFILE_FILE}" 2>/dev/null || true
}

# Makefile 是否有某个 target
_mrcfg_make_target() {
	local root="$1" target="$2"
	[ -f "${root}/Makefile" ] || return 1
	grep -qE "^${target}:" "${root}/Makefile" 2>/dev/null
}

# ------------------------------------------------------------------ 初始化

mrcfg_init() {
	local start="${1:-$PWD}"
	MRC_ROOT="$(mrcfg_find_root "$start")" || {
		echo "无法定位仓库根（未找到 .git / go.mod）: ${start}" >&2
		return 1
	}
	MRC_PROFILE_FILE="$(mrcfg_find_profile "${MRC_ROOT}")"
	MRC_MODULE="$(mrcfg_module)"
	MRC_MAIN_BRANCH="$(mrcfg_get '.branches.main' 'master')"
	MRC_SERVICE_GLOB="$(mrcfg_get '.service_glob' '')"
	# 供 lib/git.sh 的 infer_mr_base 兜底使用
	export MRC_MAIN_BRANCH
	printf '%s' "${MRC_ROOT}"
}

# 模块路径：profile.module → go.mod 的 module 行
mrcfg_module() {
	local m
	m="$(mrcfg_get '.module' '')"
	if [ -z "$m" ] && [ -f "${MRC_ROOT}/go.mod" ]; then
		m=$(sed -n 's/^module[[:space:]]\+//p' "${MRC_ROOT}/go.mod" | head -n 1 | tr -d '"')
	fi
	printf '%s' "$m"
}

# ------------------------------------------------------------------ 服务 / 构建

# 规格字符串（空格/逗号分隔）→ 每行一个，供 while read 安全迭代
# （直接 `for x in $spec` 会做路径通配展开，app/* 会变成 app/xxx 列表）
_mrcfg_lines() { printf '%s' "${1:-}" | tr ',' ' ' | tr ' ' '\n' | sed '/^[[:space:]]*$/d'; }

# 服务名提取：changed files → 空格分隔服务名
# 默认按 profile.service_glob（如 app/*）；未配置时自动探测 app/ 或顶层 go.mod 目录
mrcfg_services_from_files() {
	local files="$1"
	local glob="${MRC_SERVICE_GLOB}"
	[ -n "$glob" ] || glob="$(_mrcfg_detect_service_glob)"
	[ -n "$glob" ] || return 0
	local out="" f rest svc pat prefix
	while IFS= read -r pat; do
		[ -n "$pat" ] || continue
		prefix="${pat%%\**}"
		while IFS= read -r f; do
			[ -n "$f" ] || continue
			case "$f" in
			"${prefix}"*) rest="${f#"${prefix}"}" ;;
			*) continue ;;
			esac
			case "$rest" in
			*/*) svc="${rest%%/*}" ;;
			*) continue ;; # 前缀下的顶层文件，不属于某个服务
			esac
			[ -n "$svc" ] && out="${out}${svc}\n"
		done <<EOF
${files}
EOF
	done <<EOF
$(_mrcfg_lines "$glob")
EOF
	printf '%b' "$out" | sort -u | tr '\n' ' ' | sed 's/ *$//'
}

_mrcfg_detect_service_glob() {
	if [ -d "${MRC_ROOT}/app" ]; then
		echo "app/*"
		return 0
	fi
	# 顶层出现 go.mod 的多模块仓库
	local glue=""
	local d
	for d in "${MRC_ROOT}"/*/; do
		[ -f "${d}go.mod" ] || continue
		glue="${glue} $(basename "$d")/*"
	done
	if [ -n "$glue" ]; then
		echo "$glue"
	fi
	return 0
}

# 服务目录：profile.service_dir 模板（{name} 占位）→ 逐个候选探测
mrcfg_service_dir() {
	local svc="$1"
	local tpl cand
	tpl="$(mrcfg_get '.service_dir' 'app/{name}/service')"
	for cand in "${tpl//\{name\}/$svc}" "${svc}" "app/${svc}" "."; do
		if [ -d "${MRC_ROOT}/${cand}" ]; then
			printf '%s' "$cand"
			return 0
		fi
	done
	return 1
}

# 编译命令：profile.build_cmd → make build NAME=<svc> → go build ./...
mrcfg_build_cmd() {
	local svc="$1"
	local cmd
	cmd="$(mrcfg_get '.build_cmd' '')"
	if [ -n "$cmd" ]; then
		printf '%s' "${cmd//\{name\}/$svc}"
		return 0
	fi
	if _mrcfg_make_target "${MRC_ROOT}" build; then
		printf 'make build NAME=%s' "$svc"
	elif [ -f "${MRC_ROOT}/go.mod" ]; then
		printf 'go build ./...'
	fi
}

# 代码生成命令：profile.codegen_cmd → make all（Makefile 有该 target 时）→ 空
mrcfg_codegen_cmd() {
	local cmd
	cmd="$(mrcfg_get '.codegen_cmd' '')"
	if [ -n "$cmd" ]; then
		printf '%s' "$cmd"
		return 0
	fi
	if _mrcfg_make_target "${MRC_ROOT}" all; then
		printf 'make all'
	fi
}

# 测试命令：profile.test_cmd → go test ./...
mrcfg_test_cmd() {
	local cmd
	cmd="$(mrcfg_get '.test_cmd' '')"
	if [ -n "$cmd" ]; then
		printf '%s' "$cmd"
		return 0
	fi
	if [ -f "${MRC_ROOT}/go.mod" ]; then
		printf 'go test ./...'
	fi
}

# ------------------------------------------------------------------ 插件 / 共享包 / proto

# 插件根目录下所有独立 Go module（相对仓库根），maxdepth 3
_mrcfg_plugin_all_modules() {
	local root="$1"
	[ -d "${root}" ] || return 0
	find "${root}" -maxdepth 3 -name go.mod 2>/dev/null | sed "s#^${root}/##; s#/go.mod\$##" | sort
}

# 跨模块改动（Makefile / 产物目录）→ 1，否则 0
mrcfg_plugin_all_triggered() {
	local files="$1"
	local proot glob_all g f
	proot="$(mrcfg_get '.plugin_root' 'plugin')"
	[ -d "${MRC_ROOT}/${proot}" ] || {
		echo 0
		return 0
	}
	glob_all="$(mrcfg_get '.plugin_all_globs' "${proot}/Makefile")"
	while IFS= read -r g; do
		[ -n "$g" ] || continue
		while IFS= read -r f; do
			[ -n "$f" ] || continue
			case "$f" in
			"${g}"*)
				echo 1
				return 0
				;;
			esac
		done <<EOF
${files}
EOF
	done <<EOF
$(_mrcfg_lines "$glob_all")
EOF
	echo 0
}

# changed files → 命中的插件模块（空格分隔，相对仓库根）
mrcfg_plugin_modules() {
	local files="$1"
	local proot mods hits="" f mod
	proot="$(mrcfg_get '.plugin_root' 'plugin')"
	[ -d "${MRC_ROOT}/${proot}" ] || return 0
	mods="$(_mrcfg_plugin_all_modules "${MRC_ROOT}/${proot}")"
	[ -n "$mods" ] || return 0

	# 跨模块改动无法定位单个模块 → 全部模块
	if [ "$(mrcfg_plugin_all_triggered "${files}")" = "1" ]; then
		printf '%s\n' $mods | tr '\n' ' ' | sed 's/ *$//'
		return 0
	fi

	while IFS= read -r f; do
		[ -n "$f" ] || continue
		while IFS= read -r mod; do
			[ -n "$mod" ] || continue
			case "$f" in
			"${proot}/${mod}/"*) hits="${hits}${mod}\n" ;;
			esac
		done <<EOF
${mods}
EOF
	done <<EOF
${files}
EOF
	printf '%b' "$hits" | sort -u | tr '\n' ' ' | sed 's/ *$//'
}

# 共享包反查：<shared_pkg_dir>/<pkg>/ 被哪些服务引用
mrcfg_shared_pkg_impact() {
	local pkg="$1"
	local sdir glob rev pat prefix
	sdir="$(mrcfg_get '.shared_pkg_dir' 'pkg')"
	[ -n "${MRC_MODULE}" ] || return 0
	glob="$(mrcfg_get '.service_glob' '')"
	[ -n "$glob" ] || glob="$(_mrcfg_detect_service_glob)"
	[ -n "$glob" ] || return 0
	rev="${MRC_REV:-HEAD}"
	# 路径通配必须带 **：git grep 对 'app/*/service' 这种目录本身不命中其下文件
	local paths=()
	while IFS= read -r pat; do
		[ -n "$pat" ] || continue
		paths+=("${pat%%\**}**")
	done <<EOF
$(_mrcfg_lines "$glob")
EOF
	[ ${#paths[@]} -eq 0 ] && return 0
	# 匹配 import 路径 `.../pkg/<name>"` 与 `.../pkg/<name>/xxx"` 两种形态
	git -C "${MRC_ROOT}" grep -lE "\"${MRC_MODULE}/${sdir}/${pkg}[\"/]" "$rev" -- "${paths[@]}" 2>/dev/null |
		sed 's/^[^:]*://' |
		while IFS= read -r f; do
			[ -n "$f" ] || continue
			local rest="$f" match=""
			while IFS= read -r pat; do
				[ -n "$pat" ] || continue
				prefix="${pat%%\**}"
				case "$f" in
				"${prefix}"*) rest="${f#"${prefix}"}" ;match=1 ;;
				esac
				[ -n "$match" ] && break
			done <<XEOF
$(_mrcfg_lines "$glob")
XEOF
			case "$rest" in
			*/*) echo "${rest%%/*}" ;;
			esac
		done | sort -u | tr '\n' ' ' | sed 's/ *$//'
}

# proto 目录是否被改动（0/1）
mrcfg_proto_touched() {
	local files="$1"
	local dirs d f
	dirs="$(mrcfg_get '.proto_dirs' 'grpc proto')"
	while IFS= read -r d; do
		[ -n "$d" ] || continue
		while IFS= read -r f; do
			case "$f" in
			"${d}/"*) return 0 ;;
			esac
		done <<EOF
${files}
EOF
	done <<EOF
$(_mrcfg_lines "$dirs")
EOF
	return 1
}

# ------------------------------------------------------------------ 平台 / 通知

mrcfg_repo_id() { mrcfg_get '.repo_id' ''; }
mrcfg_test_branch() { mrcfg_get '.branches.test' 'test'; }
mrcfg_merge_type() { # $1 = test|default
	mrcfg_get ".merge_type.${1:-default}" "$([ "${1:-default}" = "test" ] && echo no-fast-forward || echo rebase)"
}
mrcfg_tester_name() { mrcfg_get '.tester.name' ''; }
mrcfg_tester_mobile() { mrcfg_get '.tester.mobile' ''; }
mrcfg_dingtalk_keyword() { mrcfg_get '.dingtalk.keyword' ''; }
mrcfg_recipients_file() { mrcfg_get '.recipients_file' ''; }
