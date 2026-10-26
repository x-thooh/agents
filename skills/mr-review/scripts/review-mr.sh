#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# review-mr.sh — MR 审查流水线（git worktree 隔离审查）
#
# 流程：fetch → MR 元信息 → 影响面分析 → worktree 检出 → 代码生成
#       → 服务/插件模块编译 → 测试 → diff 安全检查 → diff 导出 → 元信息输出 → 汇总报告
#
# 仓库差异全部来自 profile（见 scripts/lib/config.sh 与 config/mr-review.example.json）：
#   - codegen_cmd  代码生成（默认：Makefile 有 all target 时 make all）
#   - build_cmd    服务编译（默认：Makefile 有 build target 时 make build NAME={name}，否则 go build ./...）
#   - test_cmd     测试（默认 go test ./...）
#
# 用法:
#   review-mr.sh feature/zxp/4.3.1                 # 审查分支（自动推断 base）
#   review-mr.sh feature/zxp/4.3.1 --base origin/feature/v4.3.1     # 显式指定 MR target
#   review-mr.sh feature/zxp/4.3.1 --remote upstream                # 指定非默认 remote
#   .../review-mr.sh feature/zxp/4.3.1 --no-tests                   # 只编译不跑测试
#   .../review-mr.sh feature/zxp/4.3.1 --no-codegen                 # 跳过代码生成
#   .../review-mr.sh feature/zxp/4.3.1 --keep                       # 审查后保留 worktree
#   .../review-mr.sh feature/zxp/4.3.1 --cleanup                    # 删除已存在的同名 worktree
# ==============================================================================

# 从脚本位置向上查找仓库根（Makefile + go.mod 同时存在即根），保证任意 cwd 可运行
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/config.sh
source "${SCRIPT_DIR}/lib/config.sh"
# shellcheck source=lib/git.sh
source "${SCRIPT_DIR}/lib/git.sh"
# 仓库根：从 cwd 向上找（.git / go.mod），任意 cwd 可运行
mrcfg_init "${PWD}" >/dev/null || exit 1
ROOT_DIR="${MRC_ROOT}"
if [ -n "${MRC_PROFILE_FILE:-}" ]; then
	echo "profile: ${MRC_PROFILE_FILE}"
else
	echo "profile: 无（走内置默认；可写 <repo>/.mr-review.json 定制，模板见 config/mr-review.example.json）"
fi
cd "${ROOT_DIR}"

# ---------- 参数解析 ----------
BRANCH=""
BASE=""
REMOTE="origin"
SERVICES=""
KEEP=0
CLEANUP=0
DO_CODEGEN=1
DO_TESTS=1

while [ $# -gt 0 ]; do
	case "$1" in
	--base)
		BASE="$2"
		shift 2
		;;
	--remote)
		REMOTE="$2"
		shift 2
		;;
	--services)
		SERVICES="$2"
		shift 2
		;;
	--keep)
		KEEP=1
		shift
		;;
	--cleanup)
		CLEANUP=1
		shift
		;;
	--no-codegen)
		DO_CODEGEN=0
		shift
		;;
	--no-tests)
		DO_TESTS=0
		shift
		;;
	-h | --help)
		grep '^#' "$0" | sed 's/^# \{0,2\}//' | grep -v '^='
		exit 0
		;;
	-*)
		echo "未知参数: $1"
		exit 1
		;;
	*)
		BRANCH="$1"
		shift
		;;
	esac
done

if [ -z "${BRANCH}" ]; then
	echo "用法: $0 <branch> [--base <ref>] [--remote <remote>] [--services \"a b c\"] [--keep|--cleanup] [--no-codegen] [--no-tests]"
	exit 1
fi

# ---------- 环境准备 ----------
# 读取项目 AGENTS.md 中的私有模块/代理配置；若未定义则使用通用默认值
if [ -f "${ROOT_DIR}/AGENTS.md" ]; then
	AGENTS_GOPRIVATE=$(sed -n 's/^GOPRIVATE=\s*"\?\([^"]*\)"\?$/\1/p' "${ROOT_DIR}/AGENTS.md" | head -n 1)
	AGENTS_GOPROXY=$(sed -n 's/^GOPROXY=\s*"\?\([^"]*\)"\?$/\1/p' "${ROOT_DIR}/AGENTS.md" | head -n 1)
	AGENTS_GOPATH=$(sed -n 's/^GOPATH=\s*"\?\([^"]*\)"\?$/\1/p' "${ROOT_DIR}/AGENTS.md" | head -n 1)
fi
export GOPRIVATE="${AGENTS_GOPRIVATE:-gitea.cdlsxd.cn}"
export GOPROXY="${AGENTS_GOPROXY:-https://goproxy.cn,direct}"
MAIN_GO_DIR="${AGENTS_GOPATH:-${ROOT_DIR}/.go}"
if [ -d "${MAIN_GO_DIR}" ]; then
	export GOPATH="${MAIN_GO_DIR}"
	export GOBIN="${MAIN_GO_DIR}/bin"
	export PATH="${GOBIN}:${PATH}"
fi
# buf / wire / protoc 插件路径：优先用 AGENTS.md 中的全局 bin，其次推断
GLOBAL_BIN_CANDIDATES=("/Users/thooh/go/bin" "${GOPATH}/bin" "${HOME}/go/bin")
for cand in "${GLOBAL_BIN_CANDIDATES[@]}"; do
	if [ -d "${cand}" ]; then
		export PATH="${cand}:${PATH}"
	fi
done

# 若分支名首段已是已知 remote（如 origin/、upstream/），直接使用；否则补 remote/
if git remote | grep -qxF "${BRANCH%%/*}"; then
	REMOTE_BRANCH="${BRANCH}"
else
	REMOTE_BRANCH="${REMOTE}/${BRANCH}"
fi
WORKTREE_DIR="${ROOT_DIR}/../mr-${BRANCH//\//_}-review"
TMP_DIFF="/tmp/mr-${BRANCH//\//_}.diff"
START_TS=$(date +%s) # Trace：记录流水线开始时间，汇总输出总耗时

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'
ok() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; }

if ! git fetch "${REMOTE}" --prune >/dev/null 2>&1; then
	warn "git fetch ${REMOTE} 失败，可能基于过期 refs 推断 base"
fi

if [[ -z "${BASE}" ]]; then
	BASE=$(infer_mr_base "${REMOTE_BRANCH}" "${REMOTE}")
	warn "未指定 --base，自动推断 MR target: ${BASE}"
fi

# ---------- Phase 0: MR 元信息 ----------
echo ""
echo "=============================================="
echo "Phase 0: MR 元信息"
echo "=============================================="

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
echo "current_branch: ${CURRENT_BRANCH}"
echo "remote_branch:  ${REMOTE_BRANCH}"
echo "base:           ${BASE}"

if git rev-parse --verify "${BASE}" >/dev/null 2>&1 && git rev-parse --verify "${REMOTE_BRANCH}" >/dev/null 2>&1; then
	AHEAD_BEHIND=$(git rev-list --left-right --count "${BASE}...${REMOTE_BRANCH}" 2>/dev/null || echo "unknown")
	echo "ahead_behind:   ${AHEAD_BEHIND}"
else
	echo "ahead_behind:   unable-to-compute"
fi

echo ""
echo "--- 提交列表 ---"
if git rev-parse --verify "${REMOTE_BRANCH}" >/dev/null 2>&1 && git rev-parse --verify "${BASE}" >/dev/null 2>&1; then
	git log --oneline --reverse "${BASE}..${REMOTE_BRANCH}" | cat
else
	warn "无法获取提交列表（refs 缺失）"
fi

echo ""
echo "--- 提交详情（含作者） ---"
if git rev-parse --verify "${REMOTE_BRANCH}" >/dev/null 2>&1 && git rev-parse --verify "${BASE}" >/dev/null 2>&1; then
	git log --format='%h|%an|%ae|%ai|%s' "${BASE}..${REMOTE_BRANCH}" 2>/dev/null || echo "no commits"
else
	echo "missing refs"
fi

echo ""
echo "--- 文件变更统计 ---"
if git rev-parse --verify "${BASE}" >/dev/null 2>&1 && git rev-parse --verify "${REMOTE_BRANCH}" >/dev/null 2>&1; then
	NUMSTAT=$(git diff --numstat "${BASE}...${REMOTE_BRANCH}" 2>/dev/null || echo "")
	if [ -n "${NUMSTAT}" ]; then
		FILES=$(echo "${NUMSTAT}" | wc -l | tr -d ' ')
		INS=$(echo "${NUMSTAT}" | awk -F'\t' 'NF==3{sum+=$1} END{printf "%s", sum}')
		DEL=$(echo "${NUMSTAT}" | awk -F'\t' 'NF==3{sum+=$2} END{printf "%s", sum}')
		echo "files=${FILES} insertions=${INS:-0} deletions=${DEL:-0}"
	else
		echo "files=0 insertions=0 deletions=0"
	fi
else
	echo "missing refs"
fi

# ---------- Phase 1: 概览 ----------
echo ""
echo "=============================================="
echo "Phase 1: 概览"
echo "=============================================="

if ! git rev-parse --verify "${REMOTE_BRANCH}" >/dev/null 2>&1; then
	fail "远端分支不存在: ${REMOTE_BRANCH}"
	exit 1
fi

echo ""
echo "--- 改动文件 ($(git diff --name-only "${BASE}...${REMOTE_BRANCH}" | wc -l | tr -d ' ') 个) ---"
git diff --name-only "${BASE}...${REMOTE_BRANCH}"
echo ""
echo "--- 改动规模 ---"
git diff --stat "${BASE}...${REMOTE_BRANCH}" | tail -3

# ---------- Phase 1.5: 影响面分析（app 服务 / 插件模块 / 共享包 / proto） ----------
# “影响服务”不能只看服务目录（默认 app/{svc}）：
#   - 插件目录（profile.plugin_root，默认 plugin/）下是若干独立 Go module，服务级构建覆盖不到
#   - 共享包目录（profile.shared_pkg_dir，默认 pkg/）是跨服务共享代码，需反查引用方
#   - proto 目录（profile.proto_dirs，默认 grpc/ proto/）变更影响全部服务
# 这几类都不在服务目录下，只统计服务会得出「无服务变更 → 跳过编译测试」的错误结论。
CHANGED_FILES="$(git diff --name-only "${BASE}...${REMOTE_BRANCH}" 2>/dev/null || echo "")"

if [ -z "${SERVICES}" ]; then
	SERVICES="$(mrcfg_services_from_files "${CHANGED_FILES}")"
fi
SERVICES="${SERVICES% }"

# 插件模块：profile.plugin_root（默认 plugin/）下的独立 go module；跨模块改动 → 全量
PLUGIN_MODULES="$(mrcfg_plugin_modules "${CHANGED_FILES}")"
PLUGIN_ALL="$(mrcfg_plugin_all_triggered "${CHANGED_FILES}")"

# 共享包：只取 <shared_pkg_dir>/ 下的子目录包（顶层 .go 文件没有包名可反查）
SHARED_DIR="$(mrcfg_get '.shared_pkg_dir' 'pkg')"
PKG_PACKAGES="$(printf '%s\n' "${CHANGED_FILES}" | awk -F/ -v d="${SHARED_DIR}" '$1 == d && NF >= 3 {print $2}' | sort -u | tr '\n' ' ')"
PKG_PACKAGES="${PKG_PACKAGES% }"
PKG_SERVICES=""
if [ -n "${PKG_PACKAGES}" ]; then
	export MRC_REV="${REMOTE_BRANCH}" # 反查在 MR 分支的代码上做
	for _pkg in ${PKG_PACKAGES}; do
		_hit="$(mrcfg_shared_pkg_impact "${_pkg}")"
		if [ -n "${_hit}" ]; then
			PKG_SERVICES="${PKG_SERVICES} ${_hit}"
		fi
	done
	PKG_SERVICES="$(printf '%s\n' ${PKG_SERVICES} | sort -u | tr '\n' ' ')"
	PKG_SERVICES="${PKG_SERVICES% }"
fi

GRPC_TOUCHED=0
if mrcfg_proto_touched "${CHANGED_FILES}"; then
	GRPC_TOUCHED=1
fi

echo ""
echo "--- 影响服务（影响面分析；审查结论必须包含本节） ---"
echo "app 服务        : ${SERVICES:-无}"
if [ -n "${PLUGIN_MODULES}" ]; then
	echo "插件模块        : ${PLUGIN_MODULES}"
	if [ "${PLUGIN_ALL}" = "1" ]; then
		echo "  └ $(mrcfg_get '.plugin_root' 'plugin')/ 跨模块改动 → 建议全量重建插件模块"
	fi
fi
if [ -n "${PKG_PACKAGES}" ]; then
	echo "共享包 ${SHARED_DIR}/**   : ${PKG_PACKAGES}"
fi
if [ -n "${PKG_SERVICES}" ]; then
	echo "  └ 引用服务    : ${PKG_SERVICES}（公共包变更，需一并回归）"
fi
if [ "${GRPC_TOUCHED}" = "1" ]; then
	echo "proto           : 有改动 → 影响全部服务（代码生成后全量编译验证）"
fi
if [ -z "${SERVICES}" ] && [ -z "${PLUGIN_MODULES}" ] && [ -z "${PKG_PACKAGES}" ] && [ "${GRPC_TOUCHED}" = "0" ]; then
	warn "未检测到服务 / 插件模块 / 共享包 / proto 变更"
fi
if [ -z "${SERVICES}" ] && [ -n "${PLUGIN_MODULES}" ]; then
	warn "服务无变更：编译/测试阶段改跑插件模块（独立 module，服务级构建覆盖不到）"
fi

# ---------- Phase 2: worktree ----------
echo ""
echo "=============================================="
echo "Phase 2: worktree 检出"
echo "=============================================="

if [ -d "${WORKTREE_DIR}" ]; then
	if [ "${CLEANUP}" = "1" ]; then
		git worktree remove --force "${WORKTREE_DIR}" >/dev/null 2>&1
		ok "删除旧 worktree: ${WORKTREE_DIR}"
	else
		warn "worktree 已存在: ${WORKTREE_DIR}（用 --cleanup 删除重建）"
	fi
fi

if [ ! -d "${WORKTREE_DIR}" ]; then
	if git worktree add "${WORKTREE_DIR}" "${REMOTE_BRANCH}" >/dev/null 2>&1; then
		ok "worktree: ${WORKTREE_DIR}"
	else
		fail "worktree 创建失败"
		exit 1
	fi
fi

# ---------- Phase 3: 生成依赖（gitignored，worktree 里缺失） ----------
CODEGEN_CMD="$(mrcfg_codegen_cmd)"
if [ "${DO_CODEGEN}" = "1" ]; then
	echo ""
	echo "=============================================="
	echo "Phase 3: 生成依赖 (${CODEGEN_CMD:-无 codegen 命令})"
	echo "=============================================="
	CODEGEN_OK=0
	if [ -z "${CODEGEN_CMD}" ]; then
		warn "未配置代码生成命令（profile.codegen_cmd 或 Makefile 的 all target）→ 跳过"
		CODEGEN_OK=1
	elif (cd "${WORKTREE_DIR}" && mrcfg_timeout 600 bash -c "${CODEGEN_CMD}" >/tmp/review-mr-codegen.log 2>&1); then
		ok "${CODEGEN_CMD} 成功"
		CODEGEN_OK=1
	else
		warn "${CODEGEN_CMD} 失败（见 /tmp/review-mr-codegen.log），尝试从主工作区拷贝生成文件"
	fi
	# 兜底：从主工作区拷贝 gitignored 生成文件
	if [ "${CODEGEN_OK}" = "0" ]; then
		warn "拷贝主工作区生成文件（改动过的 proto 对应代码可能过期）"
		find "${ROOT_DIR}" -path '*/third_party' -prune -o \
			\( -name '*.pb.go' -o -name '*.pb.validate.go' -o -name '*.pb.enum.go' -o -name 'wire_gen.go' \) -print 2>/dev/null |
			grep -v '/\.git/' | while read -r f; do
			rel="${f#${ROOT_DIR}/}"
			mkdir -p "${WORKTREE_DIR}/$(dirname "${rel}")" && cp "${f}" "${WORKTREE_DIR}/${rel}" 2>/dev/null
		done
		ok "生成文件拷贝完成"
	fi
fi

# ---------- Phase 4: 服务/插件模块编译 + 测试 ----------
# 服务间并行执行（默认并发 4，避免 CPU 打满拖慢单服务）；单服务内 build → test 保持顺序。
# 每个服务的结果写入 /tmp/review-mr-${svc}.result，汇总阶段按原顺序统一输出。
if [ "${DO_TESTS}" = "1" ]; then
	echo ""
	echo "=============================================="
	echo "Phase 4: 编译/测试受影响服务: ${SERVICES}（并发 ${MAX_PARALLEL:-4}）"
	echo "=============================================="
	MAX_PARALLEL="${MAX_PARALLEL:-4}"
	_run_svc() {
		local svc="$1"
		local result_file="/tmp/review-mr-${svc}.result"
		local sdir bcmd tcmd
		sdir="$(mrcfg_service_dir "${svc}" || true)"
		bcmd="$(mrcfg_build_cmd "${svc}")"
		tcmd="$(mrcfg_test_cmd)"
		if [ -z "${sdir}" ] || [ ! -d "${WORKTREE_DIR}/${sdir}" ] || [ -z "${bcmd}" ]; then
			echo "SKIP" >"${result_file}"
			return
		fi
		if (cd "${WORKTREE_DIR}/${sdir}" && mrcfg_timeout 180 bash -c "${bcmd}" >/tmp/review-mr-build-${svc}.log 2>&1); then
			if [ -z "${tcmd}" ] || (cd "${WORKTREE_DIR}/${sdir}" && mrcfg_timeout 300 bash -c "${tcmd}" >/tmp/review-mr-test-${svc}.log 2>&1); then
				echo "PASS" >"${result_file}"
			else
				echo "TESTFAIL" >"${result_file}"
			fi
		else
			echo "BUILDFAIL" >"${result_file}"
		fi
	}
	_PIDS=()
	_COUNT=0
	for svc in ${SERVICES}; do
		_run_svc "${svc}" &
		_PIDS+=("$!")
		_COUNT=$((_COUNT + 1))
		if [ "${_COUNT}" -ge "${MAX_PARALLEL}" ]; then
			for _pid in "${_PIDS[@]}"; do wait "${_pid}" 2>/dev/null || true; done
			_PIDS=()
			_COUNT=0
		fi
	done
	for _pid in "${_PIDS[@]}"; do wait "${_pid}" 2>/dev/null || true; done
	PASSED=()
	FAILED=()
	for svc in ${SERVICES}; do
		_res="$(cat /tmp/review-mr-${svc}.result 2>/dev/null || echo UNKNOWN)"
		case "${_res}" in
		SKIP) warn "跳过 ${svc}（无 service 目录）" ;;
		PASS)
			ok "${svc} 全通过"
			PASSED+=("${svc}")
			;;
		TESTFAIL)
			fail "${svc} 测试失败 (log: /tmp/review-mr-test-${svc}.log)"
			FAILED+=("${svc}")
			;;
		BUILDFAIL)
			fail "${svc} 编译失败 (log: /tmp/review-mr-build-${svc}.log)"
			FAILED+=("${svc}")
			;;
		*)
			fail "${svc} 状态未知 (${_res})"
			FAILED+=("${svc}")
			;;
		esac
	done
	rm -f /tmp/review-mr-*.result

	# 插件模块（plugin_root 下每个独立 go module）：服务级构建覆盖不到，必须单独编译+测试
	_PLUGIN_TARGETS="${PLUGIN_MODULES}"
	if [ "${PLUGIN_ALL}" = "1" ]; then
		_PLUGIN_TARGETS="$(cd "${WORKTREE_DIR}" 2>/dev/null && find "$(mrcfg_get '.plugin_root' 'plugin')" -maxdepth 3 -name go.mod -exec dirname {} \; | sort | tr '\n' ' ' || true)"
	fi
	if [ -n "${_PLUGIN_TARGETS}" ]; then
		# 插件模块常依赖 gitignored 的生成代码：worktree 里缺失时模块会“假失败”，
		# 提示去掉 --no-codegen 重跑（codegen 会补齐生成文件）。
		if [ "${DO_CODEGEN}" = "0" ]; then
			warn "跳过了代码生成（--no-codegen）：插件模块依赖的生成代码可能缺失，构建结果不可信"
		fi
		_run_plugin() {
			local mod="$1"
			local key="plugin-$(echo "${mod}" | tr '/' '_')"
			local result_file="/tmp/review-mr-${key}.result"
			local dir="${WORKTREE_DIR}/${mod}"
			if [ ! -d "${dir}" ]; then
				echo "SKIP" >"${result_file}"
				return
			fi
			if (cd "${dir}" && mrcfg_timeout 300 go build ./... >/tmp/review-mr-build-${key}.log 2>&1); then
				if (cd "${dir}" && mrcfg_timeout 300 go test ./... >/tmp/review-mr-test-${key}.log 2>&1); then
					echo "PASS" >"${result_file}"
				else
					echo "TESTFAIL" >"${result_file}"
				fi
			else
				echo "BUILDFAIL" >"${result_file}"
			fi
		}
		_PPIDS=()
		_PCOUNT=0
		for mod in ${_PLUGIN_TARGETS}; do
			_run_plugin "${mod}" &
			_PPIDS+=("$!")
			_PCOUNT=$((_PCOUNT + 1))
			if [ "${_PCOUNT}" -ge "${MAX_PARALLEL}" ]; then
				for _pid in "${_PPIDS[@]}"; do wait "${_pid}" 2>/dev/null || true; done
				_PPIDS=()
				_PCOUNT=0
			fi
		done
		for _pid in "${_PPIDS[@]}"; do wait "${_pid}" 2>/dev/null || true; done
		for mod in ${_PLUGIN_TARGETS}; do
			key="plugin-$(echo "${mod}" | tr '/' '_')"
			_res="$(cat /tmp/review-mr-${key}.result 2>/dev/null || echo UNKNOWN)"
			case "${_res}" in
			SKIP) warn "跳过插件模块 ${mod}（目录不存在）" ;;
			PASS)
				ok "插件模块 ${mod} 全通过"
				PASSED+=("${mod}")
				;;
			TESTFAIL)
				fail "插件模块 ${mod} 测试失败 (log: /tmp/review-mr-test-${key}.log)"
				FAILED+=("${mod}")
				;;
			BUILDFAIL)
				fail "插件模块 ${mod} 编译失败 (log: /tmp/review-mr-build-${key}.log)"
				FAILED+=("${mod}")
				;;
			*)
				fail "插件模块 ${mod} 状态未知 (${_res})"
				FAILED+=("${mod}")
				;;
			esac
		done
		rm -f /tmp/review-mr-plugin-*.result
		warn "插件模块用例多为证书/外部接口依赖：失败需与 ${BASE} 对比区分预存问题（仅本 MR 引入才算回归）"
	fi
fi

# ---------- Phase 4.5: diff 安全检查（SecurityChecker 子 Skill，对应状态机 CHECKING_SECURITY） ----------
# 轻量前置扫描，只提示不阻断；命中行供 Agent 人工核对，确认属实后按 P1/P2 写入审查结论
git diff "${BASE}...${REMOTE_BRANCH}" >"${TMP_DIFF}"
SECURITY_FILE="/tmp/mr-${BRANCH//\//_}.security.txt"
echo ""
echo "=============================================="
echo "Phase 4.5: diff 安全检查 (scan-security.sh)"
echo "=============================================="
if [ -f "${SCRIPT_DIR}/scan-security.sh" ]; then
	if bash "${SCRIPT_DIR}/scan-security.sh" "${TMP_DIFF}" --out "${SECURITY_FILE}" >/dev/null 2>&1; then
		if grep -q "未发现" "${SECURITY_FILE}"; then
			ok "安全检查通过"
		else
			SEC_HITS=$(grep -cE '^HIGH|^MEDIUM' "${SECURITY_FILE}" || true)
			warn "安全检查发现 ${SEC_HITS} 处可疑信号（见 ${SECURITY_FILE}，供 Agent 人工核对）"
			cat "${SECURITY_FILE}"
		fi
	else
		warn "安全检查脚本执行失败（不阻断）"
	fi
else
	warn "scan-security.sh 不存在，跳过安全检查"
fi

# ---------- Phase 5: 汇总（diff 已在 Phase 4.5 导出） ----------
echo ""
echo "=============================================="
echo "汇总"
echo "=============================================="
echo "diff: ${TMP_DIFF} ($(wc -l <"${TMP_DIFF}" | tr -d ' ') 行)"
echo "worktree: ${WORKTREE_DIR}"
if [ -f "${SECURITY_FILE:-}" ] && grep -q "未发现" "${SECURITY_FILE}" 2>/dev/null; then
	ok "安全检查: 未发现明显问题"
elif [ -f "${SECURITY_FILE:-}" ]; then
	warn "安全检查: 发现可疑信号，见 ${SECURITY_FILE}"
fi
if [ "${DO_TESTS}" = "1" ]; then
	echo "通过: ${PASSED[*]:-无}"
	if [ ${#FAILED[@]} -gt 0 ]; then
		fail "失败: ${FAILED[*]}（看对应 /tmp/review-mr-*.log）"
	else
		ok "所有受影响服务编译+测试通过"
	fi
fi

# 影响服务汇总（评审结论必须引用这一节）
_grpc_txt="否"
if [ "${GRPC_TOUCHED}" = "1" ]; then
	_grpc_txt="是"
fi
echo "影响服务: services=[${SERVICES:-无}] plugin=[${PLUGIN_MODULES:-无}] ${SHARED_DIR}=[${PKG_PACKAGES:-无}] proto=${_grpc_txt}"
if [ -n "${PKG_SERVICES}" ]; then
	echo "pkg/** 引用服务: ${PKG_SERVICES}"
fi

# ---------- Phase 5.5: 输出元信息供 Agent/云效 MCP 使用 ----------
FILES=${FILES:-0}
INS=${INS:-0}
DEL=${DEL:-0}
# git rev-list 输出 tab 分隔，JSON 字符串不允许字面 tab，转空格
AHEAD_BEHIND="${AHEAD_BEHIND//$'\t'/ }"
REMOTE_URL=$(git remote get-url "${REMOTE}" 2>/dev/null || echo "")
REPO_PATH=$(extract_repo_path "${REMOTE_URL}" 2>/dev/null || echo "")

# 词列表 → JSON 数组（services / plugin_modules / pkg_packages 共用）
json_array() {
	local out="[]" first=1 w
	if [ -n "${1:-}" ]; then
		out="["
		for w in $1; do
			if [ "${first}" -eq 1 ]; then
				out="${out}\"${w}\""
				first=0
			else
				out="${out},\"${w}\""
			fi
		done
		out="${out}]"
	fi
	printf '%s' "${out}"
}

# SERVICES 空格分隔（如 "supplier user"）转合法 JSON 数组；插件模块/共享包同理
services_json="$(json_array "${SERVICES}")"
plugin_json="$(json_array "${PLUGIN_MODULES}")"
pkg_json="$(json_array "${PKG_PACKAGES}")"
pkg_services_json="$(json_array "${PKG_SERVICES}")"
cat >"/tmp/mr-${BRANCH//\//_}.meta.json" <<EOF
{
  "current_branch": "${CURRENT_BRANCH}",
  "remote_branch": "${REMOTE_BRANCH}",
  "base": "${BASE}",
  "ahead_behind": "${AHEAD_BEHIND}",
  "files_changed": ${FILES},
  "insertions": ${INS},
  "deletions": ${DEL},
  "services": ${services_json},
  "plugin_modules": ${plugin_json},
  "pkg_packages": ${pkg_json},
  "pkg_impact_services": ${pkg_services_json},
  "grpc_touched": ${GRPC_TOUCHED},
  "diff_file": "${TMP_DIFF}",
  "worktree": "${WORKTREE_DIR}",
  "security_report": "${SECURITY_FILE:-}",
  "duration_sec": $(($(date +%s) - START_TS)),
  "remote_url": "${REMOTE_URL}",
  "repo_path": "${REPO_PATH}"
}
EOF
echo "meta: /tmp/mr-${BRANCH//\//_}.meta.json"

# 审查建议（联动 AGENTS.md 红线，这里只打印通用提示）
echo ""
echo "--- 审查重点（对照项目 AGENTS.md / 团队约定）---"
echo "1. 构建/生成文件变更是否破坏现有生成流程"
echo "2. 错误处理：业务错误必须使用项目约定的错误体系，禁止裸 fmt.Errorf"
echo "3. 新逻辑是否放在对应版本文件中，不污染旧版本"
echo "4. 分层：调用方 → 业务层 → 数据层；跨服务只走 RPC/HTTP"
echo "5. benchmark 白名单文件不动"
echo "6. 扫描/分页逻辑是否可能漏单；金额/支付回调字段语义"
echo "7. 安全检查报告：${SECURITY_FILE:-无}（Phase 4.5，命中项供人工核对）"
echo ""
echo "耗时: $(($(date +%s) - START_TS))s（Trace：完整流水线约 3-6 分钟）"

if [ "${KEEP}" = "1" ]; then
	echo ""
	ok "worktree 保留: ${WORKTREE_DIR}（审查完执行: git worktree remove --force ${WORKTREE_DIR}）"
else
	git worktree remove --force "${WORKTREE_DIR}" >/dev/null 2>&1
	git worktree prune
	echo ""
	ok "worktree 已清理"
fi

exit 0
