import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

export const recipe = 'official-ui-v1';
const replacements = [
  {
    path: 'apps/desktop/scripts/package-target.ts',
    edits: [[
      "await execute(invocation.unsigned ? ['run', 'build', '--profile', 'local'] : ['run', 'build:official'], buildEnv, REPOSITORY_ROOT)",
      "await execute(['run', 'build:official'], buildEnv, REPOSITORY_ROOT)",
    ]],
  },
  {
    path: 'apps/desktop/scripts/pack-local-packages.ts',
    edits: [
      ['Stage local-branded DSH packages for unsigned Desktop builds without a publication record.',
        'Stage official-profile DSH packages for unsigned Desktop builds without a publication record.'],
      ['  repositoryClientBuildEnvironment,\n  resolveClientBuildEnvironment,', '  officialClientBuildEnvironment,'],
      ["resolveClientBuildEnvironment(repositoryClientBuildEnvironment(root), 'local')", 'officialClientBuildEnvironment(root)'],
    ],
  },
];

function git(source, args) {
  return execFileSync('git', args, { cwd: source, encoding: 'utf8' }).trimEnd();
}

function expectedFiles(source) {
  const localPack = replacements[1].path;
  if (git(source, ['ls-tree', '--name-only', 'HEAD', '--', localPack]) === '') {
    const target = execFileSync('git', ['show', `HEAD:${replacements[0].path}`], { cwd: source, encoding: 'utf8' });
    const officialStages = [
      "await execute(['run', 'build:official'], buildEnv, REPOSITORY_ROOT)",
      "await execute(['run', 'release:pack', '--family', 'dsh', '--out', buildPaths.packedDsh, ...packArguments], buildEnv, REPOSITORY_ROOT)",
    ];
    if (existsSync(resolve(source, localPack)) || !officialStages.every(stage => target.split(stage).length === 2)) {
      throw new Error('Unsupported upstream source; expected official build and package stages');
    }
    return [];
  }
  return replacements.map(({ path, edits }) => {
    const original = execFileSync('git', ['show', `HEAD:${path}`], { cwd: source, encoding: 'utf8' });
    let patched = original;
    for (const [before, after] of edits) {
      if (patched.split(before).length !== 2) throw new Error(`Unsupported upstream source in ${path}; review the official UI patch`);
      patched = patched.replace(before, after);
    }
    return { path, original, patched };
  });
}

export function verifyOfficialUiPatch(source) {
  const files = expectedFiles(source);
  const changed = git(source, ['diff', '--name-only', 'HEAD', '--']).split('\n').filter(Boolean).sort();
  if (JSON.stringify(changed) !== JSON.stringify(files.map(file => file.path).sort())) {
    throw new Error('Source changes differ from the official UI patch');
  }
  for (const file of files) {
    if (readFileSync(resolve(source, file.path), 'utf8') !== file.patched) {
      throw new Error(`Unexpected source changes in ${file.path}`);
    }
  }
  const digest = bytes => createHash('sha256').update(bytes).digest('hex');
  return {
    recipe,
    files: files.map(file => ({ path: file.path, upstream_sha256: digest(file.original), patched_sha256: digest(file.patched) })),
  };
}

function apply(source) {
  if (git(source, ['diff', '--name-only', 'HEAD', '--']) !== '') throw new Error('Apply the official UI patch to a clean source checkout');
  const files = expectedFiles(source);
  for (const file of files) writeFileSync(resolve(source, file.path), file.patched);
  verifyOfficialUiPatch(source);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const [mode, sourceArgument] = process.argv.slice(2);
  if (!sourceArgument) throw new Error('Expected apply|verify SOURCE');
  const source = resolve(sourceArgument);
  if (mode === 'apply') apply(source);
  else if (mode === 'verify') verifyOfficialUiPatch(source);
  else throw new Error('Expected apply|verify SOURCE');
  console.log(`${recipe}: ${mode} succeeded`);
}
