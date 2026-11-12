import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toHash, fromHash } from '../src/lib/routes.js';

const cases = [
  [{ screen: 'landing' }, '#/'],
  [{ screen: 'entrar' }, '#/entrar'],
  [{ screen: 'crear' }, '#/crear-cuenta'],
  [{ section: 'chat' }, '#/chat'],
  [{ section: 'historial' }, '#/historial'],
  [{ section: 'ajustes' }, '#/ajustes'],
  [{ section: 'ajustes', settingsPage: 'suscripcion' }, '#/ajustes/suscripcion'],
  [{ section: 'ayudas', route: { name: 'detail', id: 'cap_coupled_sheep_goat_meat' } }, '#/ayuda/cap_coupled_sheep_goat_meat'],
  [{ section: 'ayudas', route: { name: 'guide', id: 'a b' } }, '#/ayuda/a%20b/solicitar'],
  [{ section: 'ayudas', route: { name: 'alternatives', id: 'x' } }, '#/ayuda/x/alternativas'],
];

test('every page has an address and it reads back to the same page', () => {
  for (const [loc, hash] of cases) {
    assert.equal(toHash(loc), hash);
    const back = fromHash(hash);
    assert.equal(toHash(back), hash, hash);
  }
  assert.deepEqual(fromHash('#/ayuda/a%20b/solicitar').route, { name: 'guide', id: 'a b' });
});

test('empty or unknown addresses are rejected', () => {
  assert.equal(fromHash(''), null);
  assert.equal(fromHash('#/nope'), null);
  assert.equal(fromHash('#/ajustes/hack'), null);
  assert.equal(fromHash('#/ayuda/x/otra'), null);
  assert.equal(fromHash('#/chat/extra'), null);
  assert.deepEqual(fromHash('#/chat/'), { screen: 'app', section: 'chat', settingsPage: null, route: null });
});
