import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { basename, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { verifyOfficialUiPatch } from './official-ui.mjs';

const [mode, sourceArgument, artifactArgument, outputArgument] = process.argv.slice(2);
const source = resolve(sourceArgument);
const rootManifest = JSON.parse(await readFile(join(source, 'package.json'), 'utf8'));
const desktopManifest = JSON.parse(await readFile(join(source, 'apps/desktop/package.json'), 'utf8'));
const version = process.env.BUILD_VERSION;
const tag = process.env.BUILD_UPSTREAM_TAG;
const commit = process.env.BUILD_SOURCE_SHA;
if (!version || !tag || !/^[0-9a-f]{40}$/.test(commit ?? '')) throw new Error('Missing build identity');
if (tag !== `dsh-v${version}` || rootManifest.version !== version || desktopManifest.version !== version) throw new Error('Source versions do not match the selected tag');
if (execFileSync('git', ['rev-parse', 'HEAD'], { cwd: source, encoding: 'utf8' }).trim() !== commit) throw new Error('Checked-out commit differs from the resolved upstream commit');
if (mode === 'verify') {
  execFileSync('git', ['diff', '--exit-code', 'HEAD', '--'], { cwd: source, stdio: 'inherit' });
  process.exit(0);
}
if (mode !== 'record') throw new Error('Unknown metadata mode');
const sourcePatch = verifyOfficialUiPatch(source);
const { readClientBuildRecord, officialClientBuildEnvironment } = await import(pathToFileURL(join(source, 'scripts/client-build-environment.ts')).href);
const clientBuild = readClientBuildRecord(source, officialClientBuildEnvironment(source));
const artifact = resolve(artifactArgument);
const output = resolve(outputArgument);
const filename = `deepseek-harness-${version}-mac-arm64-unsigned.dmg`;
if (basename(artifact) !== filename || !(await stat(artifact)).isFile()) throw new Error('Unexpected DMG');
const hash = createHash('sha256');
for await (const chunk of createReadStream(artifact)) hash.update(chunk);
const digest = hash.digest('hex');
const runUrl = `https://github.com/${process.env.GITHUB_REPOSITORY}/actions/runs/${process.env.GITHUB_RUN_ID}`;
const metadata = {
  schema_version: 1,
  build_recipe: sourcePatch.recipe,
  source_patch: sourcePatch,
  client: { profile: 'official', title: clientBuild.environment.DSH_CLIENT_TITLE, environment: clientBuild.environment, artifacts: clientBuild.artifacts },
  version,
  upstream: { repository: 'deepseek-ai/deepseek-harness', tag, commit, release_url: `https://github.com/deepseek-ai/deepseek-harness/releases/tag/${tag}` },
  target: { platform: 'darwin', arch: 'arm64' },
  application: { name: 'DeepSeek Harness.app', bundle_id: 'com.deepseek.harness' },
  artifact: { name: filename, sha256: digest, size: (await stat(artifact)).size },
  signing: 'ad-hoc',
  automatic_updates: false,
  builder: { repository: process.env.GITHUB_REPOSITORY, commit: process.env.GITHUB_SHA, run_id: process.env.GITHUB_RUN_ID, run_attempt: process.env.GITHUB_RUN_ATTEMPT, run_url: runUrl, node: process.version, pnpm: execFileSync('pnpm', ['--version'], { cwd: source, encoding: 'utf8' }).trim() },
  created_at: new Date().toISOString(),
};
await mkdir(output, { recursive: true });
const metadataBytes = `${JSON.stringify(metadata, null, 2)}\n`;
await writeFile(join(output, 'build-info.json'), metadataBytes);
await writeFile(join(output, 'SHA256SUMS'), `${digest}  ${filename}\n${createHash('sha256').update(metadataBytes).digest('hex')}  build-info.json\n`);
