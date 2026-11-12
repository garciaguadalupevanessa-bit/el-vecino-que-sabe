import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildChatPayload, buildMessages, validateUserText, MAX_MESSAGES } from '../src/lib/history.js';
import { loadState, saveProfile, saveMessages, clearAll } from '../src/lib/storage.js';
import { safeHttpUrl, displayHost } from '../src/lib/urls.js';

function memoryStorage() {
  const m = new Map();
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), size: () => m.size };
}

test('payload ends with the user message and respects the 30 limit', () => {
  const history = [];
  for (let i = 0; i < 40; i++) history.push({ role: i % 2 ? 'assistant' : 'user', content: `m${i}` });
  history.push({ role: 'user', content: 'último' });
  const msgs = buildMessages(history);
  assert.ok(msgs.length <= MAX_MESSAGES);
  assert.equal(msgs.at(-1).content, 'último');
  assert.equal(msgs[0].role, 'user');
});

test('payload drops empty/invalid messages and trailing assistant replies; omits empty profile', () => {
  const p = buildChatPayload([{ role: 'system', content: 'x' }, { role: 'user', content: '  hola ' }, { role: 'assistant', content: 'ok' }, { role: 'user', content: '' }], {});
  assert.deepEqual(p, { messages: [{ role: 'user', content: 'hola' }] });
  assert.deepEqual(buildChatPayload([{ role: 'user', content: 'a' }], { comunidad: 'Aragón' }).profile, { region: 'Aragón' });
});

test('validateUserText', () => {
  assert.ok(validateUserText('   '));
  assert.ok(validateUserText('x'.repeat(4001)));
  assert.equal(validateUserText('x'.repeat(4000)), null);
  assert.equal(validateUserText('¿Qué ayudas hay?'), null);
});

test('storage saves, loads, survives garbage and clears', () => {
  const s = memoryStorage();
  saveProfile(s, { comunidad: 'Aragón' });
  saveMessages(s, [{ role: 'user', content: 'hola' }, { role: 'hacker', content: 'x' }]);
  assert.deepEqual(loadState(s).profile, { comunidad: 'Aragón' });
  assert.equal(loadState(s).messages.length, 1);
  s.setItem('evqs.profile.v1', '{not json');
  assert.deepEqual(loadState(s).profile, {});
  clearAll(s);
  assert.equal(s.size(), 0);
  assert.deepEqual(loadState(null), { profile: {}, messages: [], results: null });
});

test('only http(s) links are allowed', () => {
  assert.equal(safeHttpUrl('javascript:alert(1)'), null);
  assert.equal(safeHttpUrl('data:text/html,<b>'), null);
  assert.equal(safeHttpUrl('no es url'), null);
  assert.equal(safeHttpUrl('https://www.fega.gob.es/es'), 'https://www.fega.gob.es/es');
  assert.equal(displayHost('https://www.fega.gob.es/es'), 'fega.gob.es');
});
