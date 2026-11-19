import { workerContinuity } from './worker-continuity.js';
// OpenCode V2 Promise plugin: model routing and private native-storage worker continuity.
function reference(model) {
  if (!model || typeof model.providerID !== 'string' || !model.providerID ||
      typeof model.id !== 'string' || !model.id) throw Error('Runtime model identity is unavailable');
  return `${model.providerID}/${model.id}${model.variant && model.variant !== 'default' ? `#${model.variant}` : ''}`;
}

export default {
  id: 'myopencodeconfig-cloud-session-router',
  async setup(ctx) {
    const cloud = new Set(ctx.options.cloudRoles);
    const local = ctx.options.localBindings;
    const observed = new Map();
    const continuity = workerContinuity(ctx);
    async function coordinator(sessionID) {
      const seen = new Set();
      for (let depth = 0; depth < 32; depth++) {
        if (seen.has(sessionID)) throw Error('Cyclic session lineage');
        seen.add(sessionID);
        const session = await ctx.session.get({ sessionID });
        if (!session.parentID) return reference(session.model ?? observed.get(sessionID));
        sessionID = session.parentID;
      }
      throw Error('Session lineage exceeds routing limit');
    }
    await ctx.tool.hook('execute.before', async event => {
      if (event.tool !== 'subagent' || !event.input || typeof event.input !== 'object') return;
      await continuity.before(event);
      const role = event.input.agent;
      if (cloud.has(role)) event.input.model = await coordinator(event.sessionID);
      else if (Object.hasOwn(local, role)) event.input.model = local[role];
    });
    await ctx.tool.hook('execute.after', continuity.after);
    await ctx.session.hook('context', async event => {
      if (!cloud.has(event.agent) && !Object.hasOwn(local, event.agent)) return;
      await continuity.context(event);
      const executor = reference(event.model);
      observed.set(event.sessionID, event.model);
      const primary = await coordinator(event.sessionID);
      event.system.push({ type: 'text', text: `RUNTIME MODEL IDENTITY (observed for this request):\nCoordinator: ${primary}\nExecutor: ${executor}\nSession: ${event.sessionID}\nUse these actual identities in stage/result visibility blocks. Cloud delegations follow the current primary session selection; local roles retain their fixed bindings. Never substitute a configured startup default for this identity.` });
    });
  },
};
