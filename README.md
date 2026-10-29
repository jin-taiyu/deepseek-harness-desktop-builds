# DeepSeek Harness Desktop personal builds

Build macOS arm64 DMGs from published `deepseek-ai/deepseek-harness` release tags. The source commit and every artifact checksum are recorded in `build-info.json` and `SHA256SUMS`.

Upstream unsigned packaging explicitly selects the `local` client profile, which displays “DSH 本地构建” / “DSH Local Build” with a version/commit badge. This repository applies `scripts/official-ui.mjs` to select the upstream `official` profile for both the complete build and package validation. It uses the upstream brand components and title; it does not replace UI strings or change signing, update configuration, model behavior, or session storage. Older tags with the original official build and release-pack stages need no source patch. Unknown upstream code fails for review. All patched file paths and before/after SHA-256 hashes are recorded, and artifact creation requires a valid official client build record covering the built Web and client bundles.

Corrected Releases use `desktop-v<VERSION>+official.1`; the application's version remains `<VERSION>`. Existing Releases remain available. The CLI recognizes both formats and selects the newer complete build for the same product version. A scheduled run builds the corrected revision even when the older local-profile Release already exists.

These are personal builds with local ad-hoc signing. They do not have DeepSeek's Developer ID signature, Apple notarization, or the official automatic-update service. Official UI branding does not make the binary an official distribution or make it byte-for-byte identical. Release notes retain this distinction.

`Desktop` workflow runs on branches upload the verified installer as an Actions artifact for review. Only runs on `main` publish Releases. To install a published build, fully quit DeepSeek Harness, open the DMG, and replace `DeepSeek Harness.app` in Applications. Existing user data stays in place. The running application is not modified by this repository change.

```sh
bin/dsh-desktop check
bin/dsh-desktop build --wait
bin/dsh-desktop download --dest /absolute/download/directory
bin/dsh-desktop install
```

Run automation checks with `python3 -B -m unittest discover -s tests -v` (Node.js, Git, and jq are required). Packaging uses the upstream pinned pnpm version and Node.js 24.
