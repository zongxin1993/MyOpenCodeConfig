import { createHash } from 'node:crypto';
import { realpath } from 'node:fs/promises';

const implementers = new Set(['local-worker', 'local-build']);
const coordinators = new Set(['cloud-workflow', 'cloud-design', 'cloud-plan']);
// Serialize read/modify/write across location instances in the native server.
const locks = new Map();
async function serial(key, fn) {
  const previous = locks.get(key) ?? Promise.resolve();
  const next = previous.catch(() => {}).then(fn);
  locks.set(key, next);
  try { return await next; } finally { if (locks.get(key) === next) locks.delete(key); }
}
const fail = (code, detail) => { throw Error(`${code}: ${detail}`); };
function modelReference(model) {
  if (!model?.providerID || !model?.id) return undefined;
  return `${model.providerID}/${model.id}${model.variant && model.variant !== 'default' ? '#' + model.variant : ''}`;
}

export function workerContinuity(ctx) {
  async function scope(sessionID) {
    let root = await ctx.session.get({sessionID});
    const caller = root; const seen = new Set();
    while (root.parentID) {
      if (seen.has(root.id) || seen.size >= 32) fail('WORKER_LINEAGE_INVALID', 'Cannot resolve coordinator');
      seen.add(root.id); root = await ctx.session.get({sessionID:root.parentID});
    }
    const directory = await realpath(root.location.directory);
    const identity = {rootID:root.id, projectID:root.projectID, directory};
    const key = ['worker', 'continuity', 'v1'].join('/') + '/' + createHash('sha256').update(JSON.stringify(identity)).digest('hex');
    return {...identity, caller, root, key};
  }
  async function load(s) {
    const record = await ctx.storage.get(s.key);
    if (record === undefined) return {version:1, rootID:s.rootID, projectID:s.projectID, directory:s.directory};
    if (record?.version !== 1 || record.rootID !== s.rootID || record.projectID !== s.projectID || record.directory !== s.directory ||
        (record.worker && (typeof record.worker.sessionID !== 'string' || !implementers.has(record.worker.role)))) {
      fail('WORKER_REGISTRY_INVALID', 'Stored routing record must be reconciled; never replace it with a guessed worker');
    }
    return record;
  }
  async function validate(s, child, role) {
    if (!child || child.parentID !== s.rootID || child.projectID !== s.projectID || child.agent !== role ||
        !implementers.has(role) || child.fork || child.time?.archived ||
        await realpath(child.location.directory) !== s.directory ||
        !ctx.options.localBindings[role] || modelReference(child.model) !== ctx.options.localBindings[role]) {
      fail('WORKER_IDENTITY', 'Child parent/project/worktree/role/model no longer matches this task; do not start a replacement');
    }
  }
  async function children(s) {
    const result = [];
    // Archived children also matter: hiding an old executor is not permission to replace it.
    for (const archived of [false, true]) {
      const seen = new Set(); let cursor; let complete = false;
      for (let i = 0; i < 32; i++) {
        const page = await ctx.session.list({parentID:s.rootID, directory:s.directory, archived, limit:100, ...(cursor ? {cursor} : {})});
        if (!Array.isArray(page.data) || !page.cursor) fail('WORKER_HISTORY_INCOMPLETE', 'Invalid host session page');
        for (const child of page.data) {
          if (child.parentID !== s.rootID || child.projectID !== s.projectID || !implementers.has(child.agent) || child.fork) continue;
          // A root may move to another task worktree. Its previous directory is a different scope.
          if (await realpath(child.location.directory) !== s.directory) continue;
          if (!result.some(old => old.id === child.id)) result.push(child);
        }
        cursor = page.cursor.next;
        if (!cursor) { complete = true; break; }
        if (seen.has(cursor)) break;
        seen.add(cursor);
      }
      if (!complete) fail('WORKER_HISTORY_INCOMPLETE', 'Session history pagination did not complete; cannot safely create a worker');
    }
    return result;
  }
  async function resolve(s, record) {
    if (record.worker) {
      let child;
      try { child = await ctx.session.get({sessionID:record.worker.sessionID}); }
      catch { fail('WORKER_UNAVAILABLE', `Registered worker ${record.worker.sessionID} cannot be read. Return the audit findings; coordinator must reconcile the host record. Do not wait for an unsolicited callback or create another worker.`); }
      await validate(s, child, record.worker.role);
      return record;
    }
    const candidates = await children(s);
    if (candidates.length > 1) fail('WORKER_AMBIGUOUS', 'Multiple native workers belong to this task; reconcile original dispatch receipts before continuing');
    if (candidates.length === 1) {
      const child = candidates[0]; await validate(s, child, child.agent);
      record.worker = {sessionID:child.id, role:child.agent, model:modelReference(child.model), source:'host-session-recovery'};
      delete record.pending;
      await ctx.storage.set(s.key, record);
    }
    return record;
  }
  return {
    async before(event) {
      if (event.tool !== 'subagent' || !implementers.has(event.input?.agent)) return;
      const s = await scope(event.sessionID);
      if (s.caller.id !== s.rootID || !coordinators.has(s.caller.agent)) fail('WORKER_COORDINATOR_ONLY', 'Return findings to the main cloud coordinator; reviewers must not dispatch implementation');
      return serial(s.key, async () => {
        const record = await resolve(s, await load(s));
        if (record.worker) {
          if (event.input.sessionID && event.input.sessionID !== record.worker.sessionID) fail('WORKER_IDENTITY', 'Requested session differs from the recorded worker');
          if (event.input.agent !== record.worker.role) fail('WORKER_IDENTITY', 'Resume the recorded implementation role');
          event.input.sessionID = record.worker.sessionID;
        } else {
          if (record.pending) fail('WORKER_DISPATCH_UNCERTAIN', 'An earlier dispatch has no confirmed receipt. Reconcile native history; do not duplicate it or wait indefinitely for a callback.');
          if (event.input.sessionID) fail('WORKER_IDENTITY', 'Requested worker is not a verified child of this task');
          record.pending = {callID:event.id, role:event.input.agent};
          await ctx.storage.set(s.key, record);
        }
      });
    },
    async after(event) {
      if (event.tool !== 'subagent' || !implementers.has(event.input?.agent)) return;
      const s = await scope(event.sessionID);
      if (s.caller.id !== s.rootID || !coordinators.has(s.caller.agent)) return;
      return serial(s.key, async () => {
        const record = await load(s);
        // An error can occur after dispatch side effects. Keep the reservation until host recovery proves a child.
        if (event.status !== 'completed') return;
        const sessionID = event.result.metadata?.sessionID;
        if (typeof sessionID !== 'string' || !sessionID) fail('WORKER_RECEIPT_MISSING', 'Host result has no structured child ID; never parse model-visible text as a receipt');
        const child = await ctx.session.get({sessionID}); await validate(s, child, event.input.agent);
        if (record.worker && record.worker.sessionID !== sessionID) fail('WORKER_IDENTITY', 'Receipt conflicts with recorded worker');
        record.worker = {sessionID, role:child.agent, model:modelReference(child.model), source:'dispatch-receipt', callID:event.id};
        delete record.pending;
        await ctx.storage.set(s.key, record);
      });
    },
    async context(event) {
      if (!ctx.options.cloudRoles.includes(event.agent)) return;
      let state;
      try {
        const s = await scope(event.sessionID);
        state = await serial(s.key, async () => {
          const record = await resolve(s, await load(s));
          return record.worker ? {status:'WORKER_READY', ...record.worker} : {status:record.pending ? 'WORKER_DISPATCH_UNCERTAIN' : 'NO_WORKER_YET'};
        });
      } catch (error) { state = {status:'WORKER_RECOVERY_BLOCKED', reason:error.message}; }
      event.system.push({type:'text', text:'PERSISTED WORKER CONTINUITY (host-verified routing, not audit/acceptance evidence):\n' + JSON.stringify(state) + '\nThe main coordinator owns dispatch and recovery. An ID-free local-worker follow-up automatically reuses the verified original worker. Independent reviewers: Return findings and evidence to the parent even if worker recovery is blocked; do not take over orchestration or stop your audit merely because the dispatch receipt is absent from your context. Do not invent IDs, start a replacement or wait indefinitely for unsolicited worker reports. A truly missing/ambiguous worker requires explicit reconciliation and, if necessary, separately authorised replacement with full handoff; existing plan and Freeze constraints remain binding.'});
    },
  };
}
