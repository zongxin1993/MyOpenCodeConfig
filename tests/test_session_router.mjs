import test from 'node:test';
import assert from 'node:assert/strict';
import plugin from '../plugins/cloud-session-router/index.js';

function fixture() {
  const sessions = new Map([
    ['root', { id: 'root', agent: 'cloud-workflow', model: { providerID: 'cloud', id: 'strong', variant: 'high' } }],
    ['review', { id: 'review', agent: 'cloud-review', parentID: 'root', model: { providerID: 'cloud', id: 'old' } }],
    ['local', { id: 'local', agent: 'local-worker', parentID: 'root', model: { providerID: 'local', id: 'fixed' } }],
  ]);
  const hooks = {};
  const ctx = { options: { cloudRoles: ['cloud-workflow', 'cloud-review'], localBindings: { 'local-worker': 'local/fixed' } },
    session: { get: async ({ sessionID }) => { const value = sessions.get(sessionID); if (!value) throw Error('missing'); return value; },
      hook: async (name, fn) => { hooks[name] = fn; } },
    tool: { hook: async (name, fn) => { hooks[name] = fn; } } };
  return { sessions, hooks, ctx };
}

test('new cloud review and same child followups use the current root selection', async () => {
  const f = fixture(); await plugin.setup(f.ctx);
  const event = { tool: 'subagent', sessionID: 'root', input: { agent: 'cloud-review', model: 'cloud/stale', sessionID: 'review', prompt: 'review' } };
  await f.hooks['execute.before'](event);
  assert.equal(event.input.model, 'cloud/strong#high');
  f.sessions.get('root').model = { providerID: 'other-cloud', id: 'selected', variant: 'max' };
  await f.hooks['execute.before'](event);
  assert.equal(event.input.model, 'other-cloud/selected#max');
  assert.equal(event.input.sessionID, 'review');
});

test('local execution remains fixed even with an inherited cloud model argument', async () => {
  const f = fixture(); await plugin.setup(f.ctx);
  const event = { tool: 'subagent', sessionID: 'root', input: { agent: 'local-worker', model: 'cloud/strong#high' } };
  await f.hooks['execute.before'](event);
  assert.equal(event.input.model, 'local/fixed');
});

test('unmanaged roles and unrelated tools remain untouched', async () => {
  const f = fixture(); await plugin.setup(f.ctx);
  for (const tool of ['subagent', 'read']) {
    const event = { tool, sessionID: 'root', input: { agent: 'other', model: 'custom/model' } };
    const before = JSON.stringify(event); await f.hooks['execute.before'](event);
    assert.equal(JSON.stringify(event), before);
  }
});

test('context exposes actual coordinator and executor, including local separation', async () => {
  const f = fixture(); await plugin.setup(f.ctx);
  const event = { sessionID: 'local', agent: 'local-worker', model: { providerID: 'local', id: 'fixed' }, system: [], messages: [], options: {}, tools: {} };
  await f.hooks.context(event);
  assert.match(event.system.at(-1).text, /cloud\/strong#high/);
  assert.match(event.system.at(-1).text, /local\/fixed/);
});

test('default variant is not forced as an unsupported named variant', async () => {
  const f = fixture(); await plugin.setup(f.ctx);
  f.sessions.get('root').model = { providerID: 'cloud', id: 'selected', variant: 'default' };
  const event = { tool: 'subagent', sessionID: 'root', input: { agent: 'cloud-review' } };
  await f.hooks['execute.before'](event);
  assert.equal(event.input.model, 'cloud/selected');
});

test('an observed root request supplies identity when the session uses its default', async () => {
  const f = fixture(); await plugin.setup(f.ctx);
  f.sessions.get('root').model = undefined;
  await f.hooks.context({ sessionID: 'root', agent: 'cloud-workflow',
    model: { providerID: 'cloud', id: 'actual', variant: 'high' }, system: [] });
  const event = { tool: 'subagent', sessionID: 'root', input: { agent: 'cloud-review' } };
  await f.hooks['execute.before'](event);
  assert.equal(event.input.model, 'cloud/actual#high');
  f.sessions.get('root').model = { providerID: 'cloud', id: 'new-selection' };
  await f.hooks['execute.before'](event);
  assert.equal(event.input.model, 'cloud/new-selection');
});

test('missing selection or cyclic lineage fails rather than using a static fallback', async () => {
  const f = fixture(); await plugin.setup(f.ctx);
  f.sessions.get('root').model = undefined;
  await assert.rejects(f.hooks['execute.before']({ tool: 'subagent', sessionID: 'root', input: { agent: 'cloud-review' } }));
  f.sessions.get('root').parentID = 'review';
  await assert.rejects(f.hooks['execute.before']({ tool: 'subagent', sessionID: 'review', input: { agent: 'cloud-review' } }));
});
