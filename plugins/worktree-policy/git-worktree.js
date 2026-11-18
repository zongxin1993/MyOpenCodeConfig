import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { realpath, lstat, readFile } from 'node:fs/promises';
import path from 'node:path';
const exec = promisify(execFile);
export function gitReadEnv() {
  const env = { ...process.env, GIT_OPTIONAL_LOCKS: '0' };
  for (const key of ['GIT_DIR', 'GIT_COMMON_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES']) delete env[key];
  return env;
}
export async function inspectWorktree(directory) {
  const cwd = await realpath(directory);
  const run = async args => (await exec('git', ['-C', cwd, ...args], {
    timeout: 10000, maxBuffer: 1024 * 1024, env: gitReadEnv(),
  })).stdout.trim();
  const [paths, superproject] = await Promise.all([
    run(['rev-parse', '--path-format=absolute', '--git-dir', '--git-common-dir', '--show-toplevel']),
    run(['rev-parse', '--show-superproject-working-tree']),
  ]);
  const [gitDir, commonDir, root] = paths.split('\n');
  if (!root || superproject) throw Error('A Git submodule is not task worktree isolation');
  const marker = await lstat(path.join(root, '.git'));
  if (marker.isSymbolicLink()) throw Error('Symlink Git marker is not worktree isolation');
  const isolated = gitDir !== commonDir && marker.isFile() &&
    gitDir.startsWith(path.join(commonDir, 'worktrees') + path.sep);
  if (isolated) {
    const backlink = (await readFile(path.join(gitDir, 'gitdir'), 'utf8')).trim();
    if (await realpath(path.resolve(gitDir, backlink)) !== await realpath(path.join(root, '.git'))) {
      throw Error('Git worktree backlink does not match registered checkout');
    }
  }
  return { isolated, directory: await realpath(root), commonDirectory: await realpath(commonDir), branch: await run(['branch', '--show-current']) };
}
