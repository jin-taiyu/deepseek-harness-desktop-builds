#!/bin/bash
set -euo pipefail

repository_root=$(cd "$(dirname "$0")/.." && pwd)
source "$repository_root/bin/dsh-desktop"
requested_tag="${UPSTREAM_TAG:-}"
if [ -n "$requested_tag" ]; then
  dsh_validate_tag "$requested_tag"
  release=$(dsh_releases "$DSH_UPSTREAM_REPO" | jq -ce --arg tag "$requested_tag" "$DSH_JQ sorted_releases(\"dsh-v\") | map(select(.tag_name == \$tag)) | last // error(\"Tag has no published upstream Release\")")
else
  release=$(dsh_latest_upstream)
fi
tag=$(printf '%s\n' "$release" | jq -er '.tag_name')
version="${tag#dsh-v}"
source_sha=$(gh api "repos/$DSH_UPSTREAM_REPO/commits/$tag" --jq .sha)
[[ "$source_sha" =~ ^[0-9a-f]{40}$ ]]
prerelease=$(printf '%s\n' "$release" | jq -r '.prerelease or (._version | split("+")[0] | contains("-"))')
own_release=$(dsh_releases "$DSH_DESKTOP_REPO" | jq -c --arg tag "desktop-v$version" '[.[] | select(.tag_name == $tag)] | first // null')
should_build=true
if [ "$own_release" != null ]; then
  if printf '%s\n' "$own_release" | jq -e --arg version "$version" "$DSH_JQ . + {_version: \$version} | select(.draft == false) | complete_build" >/dev/null; then
    manifest=$(gh release download "desktop-v$version" --repo "$DSH_DESKTOP_REPO" --pattern build-info.json --output -)
    printf '%s\n' "$manifest" | jq -e --arg sha "$source_sha" --arg tag "$tag" --arg version "$version" --arg repo "$DSH_UPSTREAM_REPO" \
      '.schema_version == 1 and .upstream.repository == $repo and .upstream.tag == $tag and .upstream.commit == $sha and .version == $version' >/dev/null || {
      dsh_fail 'Published build metadata differs from the current upstream tag; refusing to overwrite it'
      exit 1
    }
    should_build=false
  elif printf '%s\n' "$own_release" | jq -e '.draft == false' >/dev/null; then
    dsh_fail 'An incomplete published Release already exists; inspect it before rebuilding'
    exit 1
  fi
fi
{
  printf 'tag=%s\n' "$tag"
  printf 'version=%s\n' "$version"
  printf 'source_sha=%s\n' "$source_sha"
  printf 'prerelease=%s\n' "$prerelease"
  printf 'should_build=%s\n' "$should_build"
} >> "$GITHUB_OUTPUT"
printf 'Upstream: %s\nCommit: %s\nBuild needed: %s\n' "$tag" "$source_sha" "$should_build" | tee -a "$GITHUB_STEP_SUMMARY"
