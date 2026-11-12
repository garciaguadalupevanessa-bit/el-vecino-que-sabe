import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toBackendProfile, fromBackendProfile, fromBackendField } from '../src/lib/backendContract.js';
import { normalizeChatResponse, normalizeAid } from '../src/lib/aids.js';
import { buildChatPayload } from '../src/lib/history.js';

test('UI profile is sent with FarmProfile field names and values', () => {
  const ui = {
    comunidad: 'Aragón', provincia: 'Teruel', tipo_ganado: ['ovino', 'caprino'], num_cabezas: 300, sistema: 'extensivo',
    forma_juridica: 'persona_fisica', edad_titular: 29, anos_actividad: 2, hectareas_pasto: 12.5,
    inscrita_rega: true, agricultor_activo: false, objetivo: 'incorporacion',
  };
  const be = toBackendProfile(ui);
  assert.deepEqual(be, {
    region: 'Aragón', province: 'Teruel', livestock_type: ['sheep', 'goat'], head_count: 300, production_system: 'extensive',
    legal_form: 'individual', holder_age: 29, years_active: 2, pasture_hectares: 12.5,
    rega_registered: true, active_farmer: false, goal: 'start_up', farm_activities: ['livestock'],
  });
  const back = fromBackendProfile(be);
  assert.deepEqual(back, ui);
  assert.deepEqual(toBackendProfile({}), {});
  assert.equal(buildChatPayload([{ role: 'user', content: 'hola' }], {}).profile, undefined);
  assert.equal(fromBackendField('active_farmer'), 'agricultor_activo');
});

// Shape copied from backend/app/models/api.py (ChatResponse) and tools/requirements_engine.py.
const backendResponse = {
  answer: 'He encontrado 2 ayudas.',
  aids: [
    {
      id: 'cap_coupled_sheep_meat', name: 'Ayuda asociada al ovino', overall_result: 'unknown', reliability: 'verified',
      verification_method: 'human', status: 'active', scope: 'national', source_url: 'https://www.fega.gob.es/x', verified_on: '2026-11-11',
      requirements: [
        { description: 'Mínimo de 30 ovejas', status: 'met', reason: 'head_count=300 (required >= 30)', explanation_es: 'Número de cabezas: 300; la condición debe ser como mínimo 30. El dato cumple.', missing_field: null },
        { description: 'Agricultor activo', status: 'unknown', reason: 'This data is missing.', explanation_es: 'Falta indicar en el perfil: agricultor activo.', missing_field: 'active_farmer' },
      ],
    },
    { id: 'goat', name: 'Caprino', overall_result: 'not_met', reliability: 'extracted', requirements: [{ description: 'Mínimo de 10 cabras', status: 'not_met' }] },
  ],
  sources: [{ url: 'https://www.fega.gob.es/x', name: 'FEGA', verified_on: '2026-11-11' }],
  trace: [{ tool: 'search_aids', input: { region: 'Aragón', livestock_type: ['sheep'] }, ok: true }],
  coverage_notes: [{ message: 'Todavía no cubrimos ayudas autonómicas de Galicia.', territory: 'Galicia' }],
};

test('real backend response is understood (met / not_met / unknown, Spanish explanations)', () => {
  const r = normalizeChatResponse(backendResponse);
  const [a, b] = r.aids;
  assert.equal(a.nombre, 'Ayuda asociada al ovino');
  assert.equal(a.resultado, 'condicional');
  assert.equal(a.fiabilidad, 'verificada');
  assert.equal(a.ambito, 'estatal');
  assert.equal(a.fecha_verificacion, '2026-11-11');
  assert.deepEqual(a.requisitos.map((x) => x.estado), ['cumple', 'por_confirmar']);
  assert.match(a.requisitos[1].detalle, /Falta indicar/);
  assert.ok(!a.requisitos.some((x) => /required|missing/.test(x.detalle ?? '')), 'English debug reasons are never shown');
  assert.deepEqual(a.datos_faltantes, ['agricultor_activo']);
  assert.equal(b.resultado, 'no_elegible');
  assert.equal(r.sources[0].fecha_verificacion, '2026-11-11');
  assert.equal(r.trace[0].args.region, 'Aragón');
  assert.deepEqual(r.coverage, ['Todavía no cubrimos ayudas autonómicas de Galicia.']);
});

test('GET /api/aids/{id} (Aid model) is understood', () => {
  const aid = normalizeAid({
    id: 'x', name: 'Ayuda', agency: 'FEGA', scope: 'Aragón', short_description: 'Pago por cabeza', how_to_apply: ['Paso 1', 'Paso 2'],
    documents: ['REGA'], deadline: null, open: true, amount: null, reliability: 'metadata_only', source_url: 'https://fega.gob.es',
    verified_on: '2026-11-10', requirements: [{ ref: 'active_farmer' }, { description: 'Ovino', field: 'livestock_type', operator: 'in', value: ['sheep'] }],
  });
  assert.equal(aid.organismo, 'FEGA');
  assert.equal(aid.ambito, 'Aragón');
  assert.deepEqual(aid.pasos, ['Paso 1', 'Paso 2']);
  assert.equal(aid.fiabilidad, 'solo_metadatos');
  assert.equal(aid.requisitos.length, 1);
  assert.equal(aid.abierta, true);
});
