#!/bin/bash
set -euo pipefail

repository="${GITHUB_REPOSITORY:?}"
latest_commit=$(gh api "repos/$repository/commits?sha=main&per_page=1" --jq '.[0].commit.committer.date')
if [ "$(date -u +%s)" -lt "$(( $(date -u -d "$latest_commit" +%s) + 2592000 ))" ]; then exit 0; fi
path=.automation/last-maintenance
existing_sha=$(gh api "repos/$repository/git/trees/main?recursive=1" --jq ".tree[] | select(.path == \"$path\") | .sha")
content=$(date -u +%FT%TZ | base64 -w 0)
payload=$(jq -nc --arg content "$content" --arg sha "$existing_sha" \
  '{message:"Maintain scheduled Desktop builds",branch:"main",content:$content} + (if $sha == "" then {} else {sha:$sha} end)')
printf '%s\n' "$payload" | gh api --method PUT "repos/$repository/contents/$path" --input - --silent
