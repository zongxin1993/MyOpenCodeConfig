import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { realpath, lstat, readFile } from 'node:fs/promises';
import path from 'node:path';
const exec = promisify(execFile);
const implementation = new Set(['local-worker', 'local-build']);
const primary = new Set(['cloud-workflow', 'cloud-design', 'cloud-plan', 'local-build']);

export async function inspectWorktree(directory) {
  const cwd = await realpath(directory);
  const run = async args => (await exec('git', ['-C', cwd, ...args], {
    timeout: 10000, maxBuffer: 1024 * 1024, env: { ...process.env, GIT_OPTIONAL_LOCKS: '0' },
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
  return { isolated, directory: await realpath(root), branch: await run(['branch', '--show-current']) };
}

export default {
  id: 'myopencodeconfig-worktree-policy',
  async setup(ctx) {
    async function location(sessionID) {
      const session = await ctx.session.get({ sessionID });
      const info = await inspectWorktree(session.location.directory);
      return { session, info };
    }
    function requireIsolation(info) {
      if (!info.isolated) throw Error('WORKTREE_REQUIRED: create/move to a linked worktree with workflow_worktree before implementation or testing');
    }
    await ctx.tool.transform(editor => editor.add({
      name: 'workflow_worktree',
      description: 'Prepare isolated implementation using native Git worktrees and move this session. Reuses existing linked worktree. No source edits, stash/reset, merge or cleanup. After moving, stop this turn and onboard the returned directory on the next turn.',
      input: { type: 'object', properties: { name: { type: 'string', pattern: '^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$' } }, required: ['name'], additionalProperties: false },
      options: { codemode: false, permission: 'workflow_worktree' },
      async execute(input, context) {
        const { session, info } = await location(context.sessionID);
        if (!primary.has(session.agent)) throw Error('Only primary workflow entries prepare task worktrees');
        if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/.test(input.name)) throw Error('Invalid task worktree name');
        const current = await realpath(session.location.directory);
        if (info.isolated) return { content: JSON.stringify({ status: 'WORKTREE_READY', reused: true, ...info, directory: current }) };
        const result = await ctx.worktree.create({ projectID: session.projectID, from: info.directory, name: input.name });
        const isolated = await inspectWorktree(result.directory);
        requireIsolation(isolated);
        const target = await realpath(path.join(isolated.directory, path.relative(info.directory, current)));
        if (target !== isolated.directory && !target.startsWith(isolated.directory + path.sep)) throw Error('Nested project escaped worktree');
        await ctx.session.move({ sessionID: session.id, directory: target });
        return { content: JSON.stringify({ status: 'WORKTREE_READY', reused: false, source: info.directory,
          ...isolated, directory: target, next: 'Stop this turn. On the next turn use this directory, quality_onboard and inherited project rules before implementation.' }) };
      },
    }));
    await ctx.tool.hook('execute.before', async event => {
      if (event.tool === 'subagent' && event.input && implementation.has(event.input.agent)) {
        const parent = await location(event.sessionID); requireIsolation(parent.info);
        if (event.input.sessionID) {
          const child = await location(event.input.sessionID); requireIsolation(child.info);
          if (await realpath(child.session.location.directory) !== await realpath(parent.session.location.directory)) throw Error('Worker worktree differs from current task; start a new worker here');
        }
      }
      if (implementation.has(event.agent) && ['shell', 'edit', 'write', 'patch'].includes(event.tool)) {
        requireIsolation((await location(event.sessionID)).info);
      }
    });
  },
};
