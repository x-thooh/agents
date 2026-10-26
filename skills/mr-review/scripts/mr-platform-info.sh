#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# mr-platform-info.sh — 获取 Codeup MR 平台信息（绕过 MCP，直接调 OpenAPI）
#
# 依赖:
#   - curl, jq, git
#   - 环境变量 YUNXIAO_ACCESS_TOKEN (必填)
#
# 用法:
#   mr-platform-info.sh --meta /tmp/mr-xxx.meta.json
#   mr-platform-info.sh --local-id 9 --repo-id 7289138
#   mr-platform-info.sh --local-id 9 --repo-id 7289138 --with-comments --with-pipelines
#
# 输出:
#   默认输出人类可读摘要；--json 输出原始 JSON
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/codeup.sh"

usage() {
	cat <<'EOF'
Usage:
  mr-platform-info.sh --meta <meta.json>
  mr-platform-info.sh --local-id <id> --repo-id <id> [--org-id <id>]

Options:
  --meta <path>          review-mr.sh produced meta.json
  --local-id <id>        MR localId
  --repo-id <id>         Repository numeric ID
  --repo-path <path>     Repository path, e.g. lsxd/ymt/marketing
  --org-id <id>          Organization ID
  --with-comments        Fetch MR comments
  --with-pipelines       Fetch pipeline runs
  --with-members         Fetch reviewer details
  --json                 Output raw JSON instead of human-readable summary
  -h, --help             Show this help
EOF
}

main() {
	local meta_file=""
	local local_id=""
	local repo_id=""
	local repo_path=""
	local org_id=""
	local with_comments=false
	local with_pipelines=false
	local with_members=false
	local output_json=false

	while [[ $# -gt 0 ]]; do
		case "$1" in
		--meta)
			meta_file="$2"
			shift 2
			;;
		--local-id)
			local_id="$2"
			shift 2
			;;
		--repo-id)
			repo_id="$2"
			shift 2
			;;
		--repo-path)
			repo_path="$2"
			shift 2
			;;
		--org-id)
			org_id="$2"
			shift 2
			;;
		--with-comments)
			with_comments=true
			shift
			;;
		--with-pipelines)
			with_pipelines=true
			shift
			;;
		--with-members)
			with_members=true
			shift
			;;
		--json)
			output_json=true
			shift
			;;
		-h | --help)
			usage
			exit 0
			;;
		*) die "Unknown option: $1" ;;
		esac
	done

	[[ -n "$API_TOKEN" ]] || die "YUNXIAO_ACCESS_TOKEN is not set."

	# 推断 meta 文件路径
	if [[ -z "$meta_file" ]]; then
		meta_file=$(infer_meta_path)
	fi

	local source_branch=""
	local target_branch=""
	if [[ -n "$meta_file" && -f "$meta_file" ]]; then
		info "Reading meta: ${meta_file}"
		extract_meta_branches "$meta_file"
		source_branch="$META_SOURCE_BRANCH"
		target_branch="$META_TARGET_BRANCH"
	elif [[ -n "$meta_file" ]]; then
		info "Meta file not found: ${meta_file} (continuing without it)"
	fi

	org_id=$(resolve_org_id "$org_id")
	repo_id=$(resolve_repo_id "$org_id" "$repo_id" "$repo_path")
	local_id=$(resolve_local_id "$org_id" "$repo_id" "$local_id" "$source_branch" "$target_branch")

	local encoded_repo_id
	encoded_repo_id=$(urlencode_slash "$repo_id")

	info "Fetching MR info: org=${org_id} repo=${repo_id} localId=${local_id}"

	# 获取 MR 详情
	local mr_resp
	mr_resp=$(api_get_or_die "/oapi/v1/codeup/organizations/${org_id}/repositories/${encoded_repo_id}/changeRequests/${local_id}")

	# 获取 patchsets
	local patches_resp
	patches_resp=$(api_get_or_die "/oapi/v1/codeup/organizations/${org_id}/repositories/${encoded_repo_id}/changeRequests/${local_id}/diffs/patches")

	# 构建输出
	local output
	output=$(jq -n \
		--argjson mr "$mr_resp" \
		--argjson patches "$patches_resp" \
		'{
			mr: $mr,
			patchsets: $patches
		}')

	if [[ "$with_comments" == "true" ]]; then
		local comments_resp
		comments_resp=$(api_get_or_die "/oapi/v1/codeup/organizations/${org_id}/repositories/${encoded_repo_id}/changeRequests/${local_id}/comments/list")
		output=$(echo "$output" | jq --argjson comments "$comments_resp" '. + {comments: $comments}')
	fi

	if [[ "$with_pipelines" == "true" ]]; then
		# 尝试获取关联流水线（通过工作项或直接查询）
		local pipelines_resp
		pipelines_resp=$(api_get "/oapi/v1/codeup/organizations/${org_id}/repositories/${encoded_repo_id}/changeRequests/${local_id}/pipelines" 2>/dev/null || echo "[]")
		output=$(echo "$output" | jq --argjson pipelines "$pipelines_resp" '. + {pipelines: $pipelines}')
	fi

	if [[ "$with_members" == "true" ]]; then
		# 获取评审人信息
		local reviewer_ids
		reviewer_ids=$(echo "$mr_resp" | jq -r '[.reviewers[].userId] | map(select(. != null)) | join(",")')
		if [[ -n "$reviewer_ids" ]]; then
			local members_resp
			members_resp=$(api_get "/oapi/v1/platform/organizations/${org_id}/members?userIds=${reviewer_ids}" 2>/dev/null || echo "[]")
			output=$(echo "$output" | jq --argjson members "$members_resp" '. + {reviewers_detail: $members}')
		fi
	fi

	if [[ "$output_json" == "true" ]]; then
		echo "$output" | jq .
	else
		echo "$output" | jq -r '
			"## MR 信息",
			"- 标题：\(.mr.title // "N/A")",
			"- 状态：\(.mr.status // "N/A")",
			"- 源分支：\(.mr.sourceBranch // "N/A")",
			"- 目标分支：\(.mr.targetBranch // "N/A")",
			"- 创建者：\(.mr.author.name // "N/A") (\(.mr.author.email // ""))",
			"- 创建时间：\(.mr.createTime // "N/A")",
			"- 更新时间：\(.mr.updateTime // "N/A")",
			"- ahead/behind：\(.mr.ahead // 0)/\(.mr.behind // 0)",
			"- 冲突状态：\(.mr.conflictCheckStatus // "N/A")",
			"- 总评论数：\(.mr.totalCommentCount // 0)",
			"- 未解决评论：\(.mr.unResolvedCommentCount // 0)",
			"- 详情页：\(.mr.detailUrl // "N/A")",
			"",
			"## 评审人",
			(.mr.reviewers // [] | map("- \(.name) [\(.reviewOpinionStatus // "PENDING")] \(.hasReviewed // false | if . then "已审阅" else "未审阅" end)") | join("\n")),
			"",
			"## Patchsets",
			(.patchsets // [] | map("\(.patchSetName // "?") | \(.patchSetBizId // "?") | \(.createTime // "?")") | join("\n")),
			if .comments then
				"",
				"## 评论",
				(.comments // [] | map("[\(.comment_type // "?")] \(.author.name // "?"): \(.content // "")") | join("\n"))
			else empty end,
			if .pipelines then
				"",
				"## 流水线",
				(.pipelines // [] | map("- \(.status // "?") \(.name // "?") \(.buildUrl // "")") | join("\n"))
			else empty end,
			if .reviewers_detail then
				"",
				"## 评审人详情",
				(.reviewers_detail // [] | map("- \(.name) \(.email // "")") | join("\n"))
			else empty end
		'
	fi
}

main "$@"
