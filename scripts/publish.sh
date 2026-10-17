#!/bin/bash
set -euo pipefail

repository_root=$(cd "$(dirname "$0")/.." && pwd)
source "$repository_root/bin/dsh-desktop"
directory="$1"
version="$BUILD_VERSION"
upstream_tag="$BUILD_UPSTREAM_TAG"
release_tag="desktop-v$version"
artifact="deepseek-harness-$version-mac-arm64-unsigned.dmg"
release=$(jq -nc --arg version "$version" '{_version:$version}')
dsh_validate_download "$directory" "$release"
jq -e --arg sha "$BUILD_SOURCE_SHA" '.upstream.commit == $sha' "$directory/build-info.json" >/dev/null
existing=$(dsh_releases "$DSH_DESKTOP_REPO" | jq -c --arg tag "$release_tag" '[.[] | select(.tag_name == $tag)] | first // null')
if [ "$existing" != null ] && printf '%s\n' "$existing" | jq -e '.draft == false' >/dev/null; then
  dsh_fail 'Refusing to overwrite an already published Release'
  exit 1
fi
notes=$(mktemp)
trap 'rm -f "$notes"' EXIT
{
  printf 'Personal macOS arm64 build from unmodified official DeepSeek Harness Desktop source.\n\n'
  printf 'Upstream: https://github.com/%s/releases/tag/%s\n' "$DSH_UPSTREAM_REPO" "$upstream_tag"
  printf 'Source commit: %s\n' "$BUILD_SOURCE_SHA"
  printf 'Build: https://github.com/%s/actions/runs/%s\n\n' "$DSH_DESKTOP_REPO" "$GITHUB_RUN_ID"
  printf 'The application uses local ad-hoc signing. The DMG is not Developer ID signed or notarized.\n'
  printf 'This upstream packaging mode omits in-app automatic updates and mandatory-update policy. Download future DMGs from this repository\x27s Releases.\n'
  printf 'Fully quit DeepSeek Harness, open the DMG, drag DeepSeek Harness.app into Applications, and choose Replace. Eject the disk image after copying.\n'
  printf 'SHA256SUMS and build-info.json are available alongside the DMG. macOS may require first-launch approval in Privacy & Security.\n'
  printf 'This is a personal build, not an official DeepSeek binary distribution. Source archives attached by GitHub contain the build automation; the application source is at the upstream link above.\n'
} > "$notes"
if [ "$existing" = null ]; then
  gh release create "$release_tag" --repo "$DSH_DESKTOP_REPO" --target "$GITHUB_SHA" --draft \
    --title "DeepSeek Harness $version · macOS arm64 personal build" --notes-file "$notes"
else
  gh release edit "$release_tag" --repo "$DSH_DESKTOP_REPO" --notes-file "$notes"
fi
gh release upload "$release_tag" --repo "$DSH_DESKTOP_REPO" --clobber \
  "$directory/$artifact" "$directory/SHA256SUMS" "$directory/build-info.json"
uploaded=$(gh release view "$release_tag" --repo "$DSH_DESKTOP_REPO" --json assets)
printf '%s\n' "$uploaded" | jq -e --arg artifact "$artifact" \
  '[.assets[].name] as $names | [$artifact,"SHA256SUMS","build-info.json"] | all(. as $name | $names | index($name) != null)' >/dev/null
gh release edit "$release_tag" --repo "$DSH_DESKTOP_REPO" --draft=false --prerelease="$BUILD_PRERELEASE" --latest=false
printf 'Published: https://github.com/%s/releases/tag/%s\n' "$DSH_DESKTOP_REPO" "$release_tag" | tee -a "$GITHUB_STEP_SUMMARY"
