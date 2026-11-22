#!/bin/bash
set -euo pipefail

repository_root=$(cd "$(dirname "$0")/.." && pwd)
source "$repository_root/bin/dsh-desktop"
directory="$1"
version="$BUILD_VERSION"
upstream_tag="$BUILD_UPSTREAM_TAG"
release_tag="desktop-v$version$DSH_DESKTOP_RELEASE_SUFFIX"
artifact_arm64="deepseek-harness-$version-mac-arm64-unsigned.dmg"
artifact_x64="deepseek-harness-$version-mac-x64-unsigned.dmg"
release=$(jq -nc --arg version "$version" --arg tag "$release_tag" '{_version:$version,tag_name:$tag}')
for arch in arm64 x64; do
  dsh_validate_download "$directory" "$release" "$arch"
  jq -e --arg sha "$BUILD_SOURCE_SHA" --arg arch "$arch" '.upstream.commit == $sha and .target.arch == $arch' "$directory/build-info-$arch.json" >/dev/null
done
existing=$(dsh_releases "$DSH_DESKTOP_REPO" | jq -c --arg tag "$release_tag" '[.[] | select(.tag_name == $tag)] | first // null')
if [ "$existing" != null ] && printf '%s\n' "$existing" | jq -e '.draft == false' >/dev/null; then
  dsh_fail 'Refusing to overwrite an already published Release'
  exit 1
fi
notes=$(mktemp)
trap 'rm -f "$notes"' EXIT
{
  printf 'Personal macOS arm64 and Intel x86_64 builds from official DeepSeek Harness Desktop source, with a recorded packaging patch selecting the official client UI profile.\n\n'
  printf 'The sidebar uses the upstream DeepSeek Harness brand components, without the local-build label or commit badge. Product version: %s.\n' "$version"
  printf 'The +official.2 Release suffix identifies this packaging revision, which adds a separate Intel x64 DMG alongside arm64; it does not change the application version. Earlier Releases are retained.\n\n'
  printf 'Upstream: https://github.com/%s/releases/tag/%s\n' "$DSH_UPSTREAM_REPO" "$upstream_tag"
  printf 'Source commit: %s\n' "$BUILD_SOURCE_SHA"
  printf 'Build: https://github.com/%s/actions/runs/%s\n\n' "$DSH_DESKTOP_REPO" "$GITHUB_RUN_ID"
  printf 'The application uses local ad-hoc signing. The DMG is not Developer ID signed or notarized.\n'
  printf 'This upstream packaging mode omits in-app automatic updates and mandatory-update policy. Download future DMGs from this repository\x27s Releases.\n'
  printf 'Fully quit DeepSeek Harness, open the DMG, drag DeepSeek Harness.app into Applications, and choose Replace. Eject the disk image after copying.\n'
  printf 'Each architecture has its own SHA256SUMS and build-info JSON file alongside the DMGs. macOS may require first-launch approval in Privacy & Security.\n'
  printf 'This is a personal build, not an official DeepSeek binary distribution. Source archives attached by GitHub contain the build automation; the application source is at the upstream link above.\n'
} > "$notes"
if [ "$existing" = null ]; then
  gh release create "$release_tag" --repo "$DSH_DESKTOP_REPO" --target "$GITHUB_SHA" --draft \
    --title "DeepSeek Harness $version · macOS arm64 + Intel personal builds" --notes-file "$notes"
else
  gh release edit "$release_tag" --repo "$DSH_DESKTOP_REPO" --notes-file "$notes"
fi
gh release upload "$release_tag" --repo "$DSH_DESKTOP_REPO" --clobber \
  "$directory/$artifact_arm64" "$directory/build-info-arm64.json" "$directory/SHA256SUMS-arm64" \
  "$directory/$artifact_x64" "$directory/build-info-x64.json" "$directory/SHA256SUMS-x64"
uploaded=$(gh release view "$release_tag" --repo "$DSH_DESKTOP_REPO" --json assets)
printf '%s\n' "$uploaded" | jq -e --arg artifact_arm64 "$artifact_arm64" --arg artifact_x64 "$artifact_x64" \
  '[.assets[].name] as $names | [$artifact_arm64,"build-info-arm64.json","SHA256SUMS-arm64",$artifact_x64,"build-info-x64.json","SHA256SUMS-x64"] | all(. as $name | $names | index($name) != null)' >/dev/null
gh release edit "$release_tag" --repo "$DSH_DESKTOP_REPO" --draft=false --prerelease="$BUILD_PRERELEASE" --latest=false
printf 'Published: https://github.com/%s/releases/tag/%s\n' "$DSH_DESKTOP_REPO" "$release_tag" | tee -a "$GITHUB_STEP_SUMMARY"
