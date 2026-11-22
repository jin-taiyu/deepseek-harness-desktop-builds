# DeepSeek Harness Desktop personal builds

Build separate macOS arm64 and Intel x64 DMGs from published `deepseek-ai/deepseek-harness` release tags. Each architecture's source commit and artifact checksum are recorded in its `build-info-<arch>.json` and `SHA256SUMS-<arch>` files.

Upstream unsigned packaging explicitly selects the `local` client profile, which displays “DSH 本地构建” / “DSH Local Build” with a version/commit badge. This repository applies `scripts/official-ui.mjs` to select the upstream `official` profile for both the complete build and package validation. It uses the upstream brand components and title; it does not replace UI strings or change signing, update configuration, model behavior, or session storage. Older tags with the original official build and release-pack stages need no source patch. Unknown upstream code fails for review. All patched file paths and before/after SHA-256 hashes are recorded, and artifact creation requires a valid official client build record covering the built Web and client bundles.

Corrected multi-architecture Releases use `desktop-v<VERSION>+official.2`; the application's version remains `<VERSION>`. Earlier Releases, including the arm64-only `+official.1` builds, remain available. The CLI selects the native architecture for installation, and `download --arch x64` can fetch an Intel DMG from any Mac. A scheduled run builds the multi-architecture revision even when an older arm64-only Release already exists.

These are personal builds with local ad-hoc signing. They do not have DeepSeek's Developer ID signature, Apple notarization, or the official automatic-update service. Official UI branding does not make the binary an official distribution or make it byte-for-byte identical. Release notes retain this distinction.

`Desktop` workflow runs build on Apple Silicon and Intel macOS runners, then upload both verified installers as Actions artifacts for review. Only runs on `main` publish Releases. To install a published build, fully quit DeepSeek Harness, open the matching DMG, and replace `DeepSeek Harness.app` in Applications. The CLI automatically chooses the native build. Existing user data stays in place. The running application is not modified by this repository change.

```sh
bin/dsh-desktop check
bin/dsh-desktop build --wait
bin/dsh-desktop download --dest /absolute/download/directory
bin/dsh-desktop download --dest /absolute/download/directory --arch x64
bin/dsh-desktop install
```

Run automation checks with `python3 -B -m unittest discover -s tests -v` (Node.js, Git, and jq are required). Packaging uses the upstream pinned pnpm version and Node.js 24.
