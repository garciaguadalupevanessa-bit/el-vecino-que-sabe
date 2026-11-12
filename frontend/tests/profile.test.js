import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateProfile, profileSummary, starterProgress, profileToForm } from '../src/lib/profile.js';

test('validateProfile keeps valid fields with backend types', () => {
  const { profile, errors } = validateProfile({
    comunidad: ' Aragón ', provincia: 'Teruel', tipo_ganado: ['ovino', 'ovino', 'dragones'],
    num_cabezas: '300', edad_titular: '29', anos_actividad: '2', hectareas_pasto: '12,5',
    sistema: 'extensivo', inscrita_rega: 'true', agricultor_activo: '',
  });
  assert.deepEqual(errors, {});
  assert.deepEqual(profile, {
    comunidad: 'Aragón', provincia: 'Teruel', tipo_ganado: ['ovino'], num_cabezas: 300,
    edad_titular: 29, anos_actividad: 2, hectareas_pasto: 12.5, sistema: 'extensivo', inscrita_rega: true,
  });
});

test('validateProfile reports out-of-range numbers in Spanish', () => {
  const { profile, errors } = validateProfile({ num_cabezas: '-5', edad_titular: '12', anos_actividad: '81', hectareas_pasto: '-1' });
  assert.equal(errors.num_cabezas, 'Escribe un número entero entre 0 y 1.000.000.');
  assert.match(errors.edad_titular, /16 y 110/);
  assert.match(errors.anos_actividad, /0 y 80/);
  assert.ok(errors.hectareas_pasto);
  assert.deepEqual(profile, {});
});

test('unknown booleans are never sent as false', () => {
  assert.deepEqual(validateProfile({ agricultor_activo: undefined, inscrita_rega: 'no' }).profile, { inscrita_rega: false });
});

test('rejects invalid enum and too long text', () => {
  const { errors } = validateProfile({ sistema: 'hidropónico', comunidad: 'x'.repeat(61) });
  assert.ok(errors.sistema);
  assert.ok(errors.comunidad);
});

test('profileSummary builds the farm strip', () => {
  assert.equal(profileSummary({ comunidad: 'Aragón', tipo_ganado: ['ovino'], num_cabezas: 300 }), 'Aragón · Ovino · unas 300 cabezas');
  assert.equal(profileSummary({ tipo_ganado: ['ovino'] }), 'Ovino · falta ubicación y tamaño');
  assert.equal(profileSummary({}), 'Sin datos todavía');
  assert.equal(starterProgress({ comunidad: 'Aragón', num_cabezas: 0 }), 2);
});

test('profileToForm round-trips', () => {
  const p = { comunidad: 'Aragón', num_cabezas: 300, agricultor_activo: false };
  assert.deepEqual(validateProfile(profileToForm(p)).profile, p);
});
