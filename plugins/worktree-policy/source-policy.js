import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { homedir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { realpath, access } from 'node:fs/promises';
import { inspectWorktree, gitReadEnv } from './git-worktree.js';

const exec = promisify(execFile);
const roles = new Set(['cloud-workflow', 'cloud-design', 'cloud-plan', 'cloud-review',
  'cloud-plan-review', 'cloud-structure-review', 'cloud-test-review',
  'local-worker', 'local-build', 'local-inspect']);
const reading = new Set(['read']);
const inside = (value, root) => value === root || value.startsWith(root + path.sep);
async function canonical(value) {
  try { return await realpath(value); }
  catch (error) {
    if (error.code !== 'ENOENT') throw error;
    const parent = path.dirname(value);
    if (parent === value) throw error;
    return path.join(await canonical(parent), path.basename(value));
  }
}
function protectedRead(value, source) {
  if (!inside(value, source)) return false;
  const parts = path.relative(source, value).split(path.sep);
  return parts.some(p => ['.git', '.ssh', '.aws', '.config'].includes(p) || p.startsWith('.env') || /\.(pem|key)$/i.test(p));
}

export async function sourceReadPolicy(directory) {
  let info;
  try { info = await inspectWorktree(directory); }
  catch (error) {
    // Ordinary non-Git locations receive no grant. Broken/forged Git metadata must fail closed.
    if (error.code === 'ENOENT' || error.stderr?.includes('not a git repository')) return null;
    throw error;
  }
  const { stdout } = await exec('git', ['-C', info.directory, 'worktree', 'list', '--porcelain', '-z'],
    { timeout: 10000, maxBuffer: 1024 * 1024, env: gitReadEnv() });
  const first = stdout.split('\0').find(line => line.startsWith('worktree '));
  if (!first) throw Error('Missing source checkout registration');
  const source = await realpath(first.slice('worktree '.length));
  const main = await inspectWorktree(source);
  if (main.isolated || main.commonDirectory !== info.commonDirectory || source === path.parse(source).root || source === await realpath(homedir())) {
    throw Error('Unsafe or unrelated source checkout');
  }
  if (/[*?\[\]\r\n]/.test(source)) throw Error('Source path cannot be represented safely by permission patterns');
  const rules = [
    { action: 'external_directory', resource: source + '/*', effect: 'allow' },
    { action: 'edit', resource: source, effect: 'deny' },
    { action: 'edit', resource: source + '/*', effect: 'deny' },
  ];
  for (const pattern of ['.git', '.git/*', '.env*', '*/.env*', '*.pem', '*.key', '.ssh/*', '.aws/*', '.config/*']) {
    rules.push({ action: 'read', resource: source + '/' + pattern, effect: 'deny' });
  }
  return { source, worktree: info.directory, commonDirectory: info.commonDirectory, rules };
}

export async function installSourcePolicy(ctx) {
  const policy = await sourceReadPolicy(ctx.location.directory);
  if (!policy) return;
  // Configured agents are registered after package plugins. Register only once the
  // first request/tool arrives so the transform runs AFTER opencode.config.agent.
  let installed;
  const ensureApplied = () => installed ??= ctx.agent.transform(editor => {
    for (const agent of editor.list()) {
      if (!roles.has(agent.id)) continue;
      editor.update(agent.id, value => {
        const permissions = value.permissions ?? [];
        const explicitDeny = permissions.some(p => p.action === 'external_directory' && p.effect === 'deny');
        value.permissions = [...permissions, ...policy.rules.filter(p => !explicitDeny || p.action !== 'external_directory')];
      });
    }
  });
  await ctx.shell.hook('create.before', event => protectShell(event, policy));
  const calls = new Map();
  await ctx.tool.hook('execute.before', async event => {
    await ensureApplied();
    // Grep does not perform per-result read authorization in OpenCode. Do not
    // grant it a new route into source credentials; source inspection uses read.
    if (['grep', 'glob'].includes(event.tool)) {
      const target = await realpath(path.resolve(ctx.location.directory, event.input?.path ?? '.'));
      if (inside(target, policy.source) || inside(policy.source, target)) {
        throw Error('SOURCE_READ_ONLY: inspect original checkout with read, not directory-wide search');
      }
    }
    calls.set(event.sessionID + ':' + event.id, event.tool);
  });
  await ctx.tool.hook('execute.after', event => {
    calls.delete(event.sessionID + ':' + event.id);
  });
  await ctx.permission.hook('evaluate', async event => {
    if (['read', 'edit'].includes(event.action)) {
      for (const resource of event.resources) {
        const lexical = path.resolve(ctx.location.directory, resource);
        const target = await canonical(lexical);
        if ((event.action === 'edit' && inside(target, policy.source)) ||
            (event.action === 'read' && (protectedRead(target, policy.source) ||
              (inside(lexical, policy.source) && !inside(target, policy.source))))) {
          event.effect = 'deny'; event.message = 'SOURCE_READ_ONLY: protected source target'; return;
        }
      }
    }
    if (event.action !== 'external_directory' ||
        !event.resources.some(resource => inside(resource.replace(/\/\*$/, ''), policy.source))) return;
    const agent = event.agent ?? (await ctx.session.get({ sessionID: event.sessionID })).agent;
    if (!roles.has(agent)) return;
    const tool = event.source?.type === 'tool' && calls.get(event.sessionID + ':' + event.source.id);
    if (!reading.has(tool)) {
      event.effect = 'deny';
      event.message = 'SOURCE_READ_ONLY: original checkout is accessible only through read; run all mutations and tests in the worktree';
    }
  });
  await ctx.session.hook('context', async event => {
    if (!roles.has(event.agent)) return;
    await ensureApplied();
    event.system.push({ type: 'text', text: `SOURCE CHECKOUT READ-ONLY: ${policy.source}\nTask location: ${policy.worktree}\nUse direct read (including paginated directory reads) to inspect source and uncommitted baseline. Source grep/glob are blocked because host search does not check per-file read permissions. Never write back, run shell against it, or treat the bare commit as including uncommitted/untracked changes. Implement and test in the linked worktree. Credentials/Git internals remain blocked. A source read does not require asking the user to change host permissions.` });
  });
}

// Confinement must follow subprocesses: string matching cannot protect against
// relative paths, variables, symlinks or writes hidden inside test/build scripts.
export async function protectShell(event, policy) {
  if (process.platform !== 'darwin') throw Error('SOURCE_READ_ONLY: shell requires macOS sandbox-exec; no unsafe fallback');
  await access('/usr/bin/sandbox-exec');
  const literal = value => JSON.stringify(value);
  // Keep command EXACTLY unchanged for native shell AST/permission checks.
  // Only replace the executable, whose POSIX -c interface is preserved.
  const filter = `(require-all (subpath ${literal(policy.source)}) (require-not (subpath ${literal(policy.commonDirectory)})))`;
  const profile = `(version 1)(allow default)(deny file-write* ${filter})(deny file-read-data ${filter})`;
  const name = path.basename(event.shell);
  if (!['bash', 'zsh', 'sh', 'dash', 'ksh'].includes(name)) throw Error('SOURCE_READ_ONLY: unsupported shell dialect');
  const wrapper = fileURLToPath(new URL('./sandbox-shell/' + name, import.meta.url));
  await access(wrapper);
  event.env ??= {};
  event.env.MYOPENCODE_SOURCE_RO_PROFILE = profile;
  event.env.MYOPENCODE_SOURCE_RO_SHELL = event.shell;
  event.shell = wrapper;
}
