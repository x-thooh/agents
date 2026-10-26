#!/usr/bin/env bash
set -euo pipefail

warn() { echo "⚠ $*"; }

# get-mr-info.sh — 提取 MR 元信息（分支、提交、作者、文件统计）
#
# 用法:
#   get-mr-info.sh <branch> [--base <ref>] [--remote <remote>]
#   get-mr-info.sh <remote>/<branch> [--base <ref>]
#
# 示例:
#   get-mr-info.sh feature/lr/v4.3.1
#   get-mr-info.sh feature/lr/v4.3.1 --base origin/feature/v4.3.1
#   get-mr-info.sh feature/lr/v4.3.1 --remote upstream
#   get-mr-info.sh origin/feature/lr/v4.3.1 --base origin/develop
#
# --base 省略时，脚本按顺序取 target branch：
#   ① Codeup MR 的 targetBranch（需要 YUNXIAO_ACCESS_TOKEN）
#   ② 从提交历史推断（lib/git.sh 的 infer_mr_base，分支模型不依赖特定平台）
# --remote 省略时默认使用 origin。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/config.sh
source "${SCRIPT_DIR}/lib/config.sh"
# shellcheck source=lib/git.sh
source "${SCRIPT_DIR}/lib/git.sh"
mrcfg_init "${PWD}" >/dev/null || exit 1
ROOT_DIR="${MRC_ROOT}"
cd "${ROOT_DIR}"

BRANCH=""
AUTO_BASE=""
REMOTE="origin"
while [ $# -gt 0 ]; do
	case "$1" in
	--base)
		AUTO_BASE="$2"
		shift 2
		;;
	--remote)
		REMOTE="$2"
		shift 2
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
	echo "用法: $0 <branch|remote/branch> [--base <ref>] [--remote <remote>]"
	exit 1
fi

# 若分支名首段已是已知 remote（如 origin/、upstream/），直接使用；否则补 remote/
if git remote | grep -qxF "${BRANCH%%/*}"; then
	REMOTE_BRANCH="${BRANCH}"
else
	REMOTE_BRANCH="${REMOTE}/${BRANCH}"
fi

if ! git fetch "${REMOTE}" --prune >/dev/null 2>&1; then
	warn "git fetch ${REMOTE} 失败，可能基于过期 refs 推断 base"
fi
# ① 先问平台（有 token 且脚本在）；② 失败则退回本地推断
if [[ -z "${AUTO_BASE}" && -n "${YUNXIAO_ACCESS_TOKEN:-}" && -x "${SCRIPT_DIR}/mr-platform-info.sh" ]]; then
	mr_json=$("${SCRIPT_DIR}/mr-platform-info.sh" --source-branch "${REMOTE_BRANCH}" --repo-path "$(git rev-parse --show-toplevel)" --json 2>/dev/null || true)
	if [[ -n "$mr_json" ]]; then
		AUTO_BASE=$(echo "$mr_json" | jq -r '.mr.targetBranch // empty' 2>/dev/null || true)
	fi
fi
if [[ -z "${AUTO_BASE}" ]]; then
	AUTO_BASE=$(infer_mr_base "${REMOTE_BRANCH}" "${REMOTE}")
	warn "未从平台取到 target，已从提交历史推断: ${AUTO_BASE}"
fi
BASE="${AUTO_BASE}"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

echo "current_branch: ${CURRENT_BRANCH}"
echo "remote_branch:  ${REMOTE_BRANCH}"
echo "base:           ${BASE}"

# ahead/behind: <base ahead> <branch ahead>
if git rev-parse --verify "${BASE}" >/dev/null 2>&1 && git rev-parse --verify "${REMOTE_BRANCH}" >/dev/null 2>&1; then
	AHEAD_BEHIND=$(git rev-list --left-right --count "${BASE}...${REMOTE_BRANCH}" 2>/dev/null || echo "unknown")
	echo "ahead_behind:   ${AHEAD_BEHIND}"
else
	echo "ahead_behind:   unable-to-compute"
fi

echo ""
echo "# commits ---"
if git rev-parse --verify "${REMOTE_BRANCH}" >/dev/null 2>&1 && git rev-parse --verify "${BASE}" >/dev/null 2>&1; then
	git log --format='%h|%an|%ae|%ai|%s' "${BASE}..${REMOTE_BRANCH}" 2>/dev/null || echo "no commits"
else
	echo "missing refs"
fi

echo ""
echo "# files changed ---"
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
