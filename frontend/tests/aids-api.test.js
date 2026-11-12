import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeChatResponse, normalizeAid, mergeAid, shortReason, formatArgs, formatDate } from '../src/lib/aids.js';
import { sendChat, ApiError } from '../src/lib/api.js';
import { parseAnswer } from '../src/lib/text.js';
import { detectProfileQuestion, quickRepliesFor } from '../src/lib/quickReplies.js';

const sample = {
  answer: 'He encontrado 2 ayudas.',
  aids: [
    { id: 'b', nombre: 'Ayuda B', fiabilidad: 'extraida', resultado: 'no_elegible', requisitos: [{ descripcion: 'Mínimo 500 cabezas', campo: 'num_cabezas', estado: 'no_cumple' }] },
    { id: 'a', nombre: 'Ayuda A', fiabilidad: 'verificada', url_fuente: 'javascript:alert(1)', evaluacion: { resultado: 'condicional', requisitos: [{ descripcion: 'Agricultor activo', estado: 'por_confirmar' }, { descripcion: 'Ovino', estado: 'cumple' }], datos_faltantes: ['agricultor_activo'] } },
  ],
  sources: [{ url: 'https://www.fega.gob.es', nombre: 'FEGA', fecha_verificacion: '2026-11-10' }, { url: 'ftp://x' }],
  trace: [{ tool: 'search_aids', arguments: '{"comunidad":"Aragón","tipo_ganado":["ovino"]}', ok: true }, { name: 'check_eligibility', args: { aid_id: 'a', profile: {} }, status: 'error', error: 'x' }],
};

test('normalizes chat response, sorts best fit first and drops unsafe links', () => {
  const r = normalizeChatResponse(sample);
  assert.deepEqual(r.aids.map((a) => a.id), ['a', 'b']);
  assert.equal(r.aids[0].resultado, 'condicional');
  assert.equal(r.aids[0].url_fuente, null);
  assert.equal(r.aids[0].requisitos.length, 2);
  assert.equal(r.sources.length, 1);
  assert.equal(r.trace[0].args.comunidad, 'Aragón');
  assert.equal(r.trace[1].ok, false);
  assert.equal(formatArgs(r.trace[1].args), 'aid_id=a, perfil');
  assert.match(shortReason(r.aids[1]), /Mínimo 500 cabezas/);
  assert.equal(shortReason(r.aids[0]), 'Falta 1 dato por confirmar.');
});

test('derives the global result from requirement states and handles empty responses', () => {
  const aid = normalizeAid({ id: 'x', requisitos: [{ descripcion: 'a', estado: 'cumple' }] });
  assert.equal(aid.resultado, 'elegible');
  assert.equal(normalizeAid({ id: 'y', requisitos: [{ descripcion: 'sin estado' }] }).resultado, 'desconocido');
  const empty = normalizeChatResponse(null);
  assert.deepEqual(empty.aids, []);
  assert.ok(empty.answer.length > 0);
});

test('mergeAid fills gaps from the detail endpoint', () => {
  const merged = mergeAid(normalizeAid({ id: 'a', resultado: 'elegible' }), normalizeAid({ id: 'a', plazo: 'Hasta el 30 de abril', resultado: 'desconocido' }));
  assert.equal(merged.plazo, 'Hasta el 30 de abril');
  assert.equal(merged.resultado, 'elegible');
  assert.equal(formatDate('2026-11-10'), '10 de noviembre de 2026');
});

test('sendChat maps HTTP errors and timeouts to friendly ApiErrors', async () => {
  const fake = (status, body) => async () => ({ ok: status < 400, status, json: async () => body });
  const ok = await sendChat({ messages: [] }, { fetchImpl: fake(200, sample) });
  assert.equal(ok.aids.length, 2);

  await assert.rejects(sendChat({}, { fetchImpl: fake(422, { detail: [{ msg: 'x' }] }) }), (e) => e instanceof ApiError && e.kind === 'validation');
  await assert.rejects(sendChat({}, { fetchImpl: fake(502, { detail: 'Límite de uso: espera un minuto.' }) }), (e) => e.kind === 'ai' && e.message === 'Límite de uso: espera un minuto.');
  await assert.rejects(sendChat({}, { fetchImpl: async () => { throw new TypeError('Failed to fetch'); } }), (e) => e.kind === 'network');

  const hang = (_url, { signal }) => new Promise((_res, rej) => signal.addEventListener('abort', () => rej(new Error('aborted'))));
  await assert.rejects(sendChat({}, { fetchImpl: hang, timeoutMs: 20 }), (e) => e.kind === 'timeout');
});

test('parseAnswer turns text into safe blocks (no HTML)', () => {
  const blocks = parseAnswer('Hola **Ana**.\n\n- Uno <script>\n- Dos https://fega.gob.es y javascript:alert(1)');
  assert.equal(blocks[0].type, 'p');
  assert.deepEqual(blocks[0].parts[1], { type: 'strong', text: 'Ana' });
  assert.equal(blocks[1].type, 'ul');
  assert.equal(blocks[1].items[0][0].text, 'Uno <script>');
  assert.ok(blocks[1].items[1].some((p) => p.type === 'link' && p.href === 'https://fega.gob.es/'));
  assert.ok(!blocks[1].items[1].some((p) => p.type === 'link' && p.href.startsWith('javascript')));
});

test('quick replies detect profile questions', () => {
  assert.equal(detectProfileQuestion('¿Estás dado de alta como agricultor activo?'), 'agricultor_activo');
  assert.equal(detectProfileQuestion('¿Tu explotación está inscrita en el REGA?'), 'inscrita_rega');
  assert.equal(detectProfileQuestion('Aquí tienes las ayudas.'), null);
  assert.deepEqual(quickRepliesFor('¿Tienes más de 300?').map((c) => c.label), ['Sí', 'No', 'No lo sé', 'Explícamelo', 'Omitir por ahora']);
  assert.deepEqual(quickRepliesFor('Hecho.'), []);
});
