#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# git.sh — 共享 git 侧工具函数（MR target 推断 / meta 解析 / URL 路径提取）
#
# 被以下脚本引用：
#   scripts/review-mr.sh
#   scripts/get-mr-info.sh
#   scripts/lib/codeup.sh（间接：mr-platform-info.sh / sync-codeup-comment.sh）
#
# 依赖: git, jq（仅 extract_meta_branches）
# 注意: 兼容 bash 3.2（不依赖 mapfile / 关联数组）；共享分支定由 lib/config.sh 提供
# ============================================================================

# 从远程分支 refs 推断 MR target branch
# 用法: infer_mr_base <mr_ref> [remote_name]   # remote_name 默认 origin
infer_mr_base() {
	local mr_ref="$1"
	local remote_name="${2:-origin}"
	# 收集远程候选分支，排除 HEAD 和 MR 本身
	local candidates=()
	local line
	while IFS= read -r line; do
		[ -n "$line" ] && candidates+=("$line")
	done <<EOF
$(git branch -r | grep -v 'HEAD' | sed 's/^ *//' | grep "^${remote_name}/" | grep -v "^${mr_ref}$" | sort)
EOF
	local count=${#candidates[@]}
	if [ "$count" -eq 0 ]; then
		echo "${remote_name}/${MRC_MAIN_BRANCH:-master}"
		return
	fi
	local mr_name="${mr_ref#${remote_name}/}"
	# 若 MR 名称中包含版本号，优先寻找同版本的分支（feature/release/bugfix）
	if [[ "$mr_name" =~ ([0-9]+\.[0-9]+\.[0-9]+) ]]; then
		local version="${BASH_REMATCH[1]}"
		for ref in "${candidates[@]}"; do
			# 若匹配到同版本号的分支，直接返回作为 base（不检查祖先关系）
			if [[ "$ref" =~ $version ]]; then
				echo "$ref"
				return
			fi
		done
	fi
	# 未找到合适的版本分支，使用原有评分逻辑
	local best=""
	local best_score=""
	local ref
	for ref in "${candidates[@]}"; do
		[[ "$ref" == "${remote_name}/HEAD" ]] && continue
		if ! git merge-base --is-ancestor "$ref" "$mr_ref" 2>/dev/null; then
			continue
		fi
		local mb=$(git merge-base "$mr_ref" "$ref" 2>/dev/null) || continue
		local date=$(git log -1 --format='%ct' "$mb" 2>/dev/null) || continue
		local score="$date"
		local ref_name="${ref#${remote_name}/}"
		if [[ "$mr_name" == *"$ref_name"* || "$ref_name" == *"$mr_name"* ]]; then
			score=$((score + 1000000))
		fi
		if [[ -z "$best" || "$score" -gt "$best_score" ]]; then
			best="$ref"
			best_score="$score"
		fi
	done
	echo "${best:-${remote_name}/${MRC_MAIN_BRANCH:-master}}"
}

# 从 git remote URL 提取仓库路径（org/repo 或 org/team/repo，去 .git 后缀）
# 兼容: https://host/org/repo.git / git@host:org/repo.git / ssh://git@host/org/repo.git
extract_repo_path() {
	local url="$1"
	echo "$url" | sed -E 's#.*://[^/]+/##; s#[^/]*:##; s#\.git$##' | sed 's#/$##'
}

# 从当前分支推断 meta 文件路径（无分支时输出空）
infer_meta_path() {
	local current_branch
	current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
	if [[ -n "$current_branch" ]]; then
		echo "/tmp/mr-${current_branch//\//_}.meta.json"
	fi
}

# 解析 meta 文件中的 source/target 分支（剥离 origin/ / upstream/ 前缀）
# 输出到全局变量 META_SOURCE_BRANCH / META_TARGET_BRANCH；文件不存在时置空
META_SOURCE_BRANCH=""
META_TARGET_BRANCH=""
extract_meta_branches() {
	local meta_file="$1"
	META_SOURCE_BRANCH=""
	META_TARGET_BRANCH=""
	[[ -n "$meta_file" && -f "$meta_file" ]] || return 0
	local rb tb
	rb=$(jq -r '.remote_branch // empty' "$meta_file" 2>/dev/null || echo "")
	tb=$(jq -r '.base // empty' "$meta_file" 2>/dev/null || echo "")
	if [[ -n "$rb" ]]; then
		META_SOURCE_BRANCH="${rb#origin/}"
		META_SOURCE_BRANCH="${META_SOURCE_BRANCH#upstream/}"
	fi
	if [[ -n "$tb" ]]; then
		META_TARGET_BRANCH="${tb#origin/}"
		META_TARGET_BRANCH="${META_TARGET_BRANCH#upstream/}"
	fi
}
