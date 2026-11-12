import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  restoreConversations, updateCurrent, startNew, select, remove, historyEntries, titleOf, getCurrent,
  formatWhen, MAX_CONVERSATIONS,
} from '../src/lib/conversations.js';

const u = (content) => ({ id: content, role: 'user', content });
const a = (content) => ({ id: `a-${content}`, role: 'assistant', content });

test('migrates the old single chat into the first conversation', () => {
  const s = restoreConversations(null, { messages: [u('Tengo ovejas'), a('Vale'), { role: 'note', content: 'x' }], results: { aids: [1, 2] } }, 1000);
  assert.equal(s.list.length, 1);
  assert.equal(getCurrent(s).messages.length, 2);
  assert.equal(historyEntries(s)[0].aids, 2);
  assert.equal(historyEntries(s)[0].current, true);
});

test('restore ignores garbage and keeps a valid current id', () => {
  const s = restoreConversations({ currentId: 'nope', list: [{ id: 'x', updatedAt: 5, messages: [u('hola')] }, 'basura', { id: 3 }] });
  assert.equal(s.list.length, 1);
  assert.equal(s.currentId, 'x');
});

test('new conversation, switch back, delete current', () => {
  let s = restoreConversations(null, { messages: [u('Primera')] }, 1000);
  const first = s.currentId;
  const same = startNew(restoreConversations(null, {}, 1000));
  assert.equal(same.list.length, 1, 'an empty conversation is reused');

  s = startNew(s, 2000);
  assert.notEqual(s.currentId, first);
  s = updateCurrent(s, { messages: [u('Segunda'), a('ok')], results: null }, 3000);
  assert.deepEqual(historyEntries(s).map((e) => e.title), ['Segunda', 'Primera']);

  s = select(s, first);
  assert.equal(getCurrent(s).messages[0].content, 'Primera');
  s = remove(s, first);
  assert.equal(s.list.length, 1);
  assert.equal(getCurrent(s).messages[0].content, 'Segunda');
  s = remove(s, s.currentId);
  assert.equal(s.list.length, 1);
  assert.equal(historyEntries(s).length, 0);
});

test('keeps at most MAX_CONVERSATIONS, dropping the oldest', () => {
  let s = restoreConversations(null, { messages: [u('c0')] }, 0);
  for (let i = 1; i <= MAX_CONVERSATIONS + 3; i++) {
    s = startNew(s, i * 10);
    s = updateCurrent(s, { messages: [u(`c${i}`)], results: null }, i * 10 + 1);
  }
  assert.equal(s.list.length, MAX_CONVERSATIONS);
  assert.ok(!historyEntries(s).some((e) => e.title === 'c0'));
});

test('titles and dates', () => {
  assert.equal(titleOf({ messages: [] }), 'Conversación nueva');
  assert.equal(titleOf({ messages: [u('x'.repeat(80))] }).length, 58);
  const now = new Date(2026, 10, 12, 12, 0).getTime();
  assert.equal(formatWhen(new Date(2026, 10, 12, 11, 30).getTime(), now), 'hoy, 11:30');
  assert.equal(formatWhen(new Date(2026, 10, 11, 9, 5).getTime(), now), 'ayer, 09:05');
  assert.equal(formatWhen(new Date(2026, 10, 3, 18, 20).getTime(), now), '3 nov, 18:20');
});
