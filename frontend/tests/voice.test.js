import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  normalizeVoiceSettings, DEFAULT_VOICE_SETTINGS, formatDuration, pickEngine, voiceError, parseYesNo,
  extractNumber, recognizedHints, textForSpeech, speechChunks, estimateSeconds,
} from '../src/lib/voice.js';
import { transcribeAudio } from '../src/lib/api.js';

test('voice settings fall back to safe defaults', () => {
  assert.deepEqual(normalizeVoiceSettings(null), DEFAULT_VOICE_SETTINGS);
  const s = normalizeVoiceSettings({ readAloud: false, rate: 'rapida', engine: 'hack', consent: 'yes' });
  assert.equal(s.readAloud, false);
  assert.equal(s.rate, 'rapida');
  assert.equal(s.engine, 'auto');
  assert.equal(s.consent, false);
});

test('durations and engine choice', () => {
  assert.equal(formatDuration(7), '0:07');
  assert.equal(formatDuration(75.9), '1:15');
  assert.equal(pickEngine('auto', { hasSpeechRecognition: true, hasMediaRecorder: true }), 'browser');
  assert.equal(pickEngine('auto', { hasSpeechRecognition: false, hasMediaRecorder: true }), 'server');
  assert.equal(pickEngine('browser', { hasSpeechRecognition: false, hasMediaRecorder: true }), null);
  assert.equal(pickEngine('auto', { hasSpeechRecognition: false, hasMediaRecorder: false }), null);
});

test('errors are explained in words', () => {
  assert.equal(voiceError('not-allowed').kind, 'permission');
  assert.equal(voiceError('NotAllowedError').title, 'No tengo permiso para el micrófono');
  assert.equal(voiceError('no-speech').title, 'No te he oído');
  assert.equal(voiceError('network').title, 'No he podido convertir tu voz en texto');
});

test('spoken yes/no answers map to quick replies', () => {
  assert.equal(parseYesNo('Sí.'), 'Sí');
  assert.equal(parseYesNo('sí, lo soy'), 'Sí');
  assert.equal(parseYesNo('No'), 'No');
  assert.equal(parseYesNo('no lo sé'), 'No lo sé');
  assert.equal(parseYesNo('Explícamelo'), 'Explícamelo');
  assert.equal(parseYesNo('tengo trescientas ovejas en Teruel y quiero saber'), null);
});

test('recognized hints: numbers in digits or words, animals and places', () => {
  assert.equal(extractNumber('Tengo unas trescientas ovejas'), 300);
  assert.equal(extractNumber('unas 1.200 cabezas'), 1200);
  assert.equal(extractNumber('dos mil quinientas'), 2500);
  assert.equal(extractNumber('una explotación de vacas'), null);
  assert.deepEqual(recognizedHints('Tengo unas trescientas ovejas en Teruel'), ['Ovino ≈ 300 cabezas', 'Teruel']);
  assert.deepEqual(recognizedHints('Hola'), []);
});

test('text for speech drops markdown and links', () => {
  const t = textForSpeech('Mira **esto**:\n\n- Paso uno\n- Paso dos en https://fega.gob.es');
  assert.equal(t, 'Mira esto: Paso uno. Paso dos en el enlace que tienes en pantalla.');
  const chunks = speechChunks('Uno. Dos. ' + 'Tres largo. '.repeat(40), 60);
  assert.ok(chunks.every((c) => c.length <= 72));
  assert.ok(estimateSeconds('una dos tres cuatro cinco seis', 'lenta') >= estimateSeconds('una dos tres cuatro cinco seis', 'rapida'));
});

test('transcribeAudio posts the recording and maps errors', async () => {
  let sent;
  const ok = async (url, opts) => { sent = { url, opts }; return { ok: true, status: 200, json: async () => ({ text: ' Hola ' }) }; };
  const blob = new Blob(['x'], { type: 'audio/webm' });
  assert.equal(await transcribeAudio(blob, { fetchImpl: ok }), 'Hola');
  assert.equal(sent.url, '/api/transcribe');
  assert.ok(sent.opts.body instanceof FormData);
  const notFound = async () => ({ ok: false, status: 404, json: async () => ({}) });
  await assert.rejects(transcribeAudio(blob, { fetchImpl: notFound }), (e) => e.kind === 'unavailable');
  const empty = async () => ({ ok: true, status: 200, json: async () => ({ text: '' }) });
  await assert.rejects(transcribeAudio(blob, { fetchImpl: empty }), (e) => e.kind === 'empty');
});
