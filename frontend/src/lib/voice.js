// Voice chat · pure logic (no browser APIs), see "Chat por voz" V1–V6.
// Speech becomes text, the farmer checks it, and it is sent like a typed message.

export const MAX_RECORDING_S = 60;
export const SILENCE_STOP_S = 3;

export const RATES = [
  { value: 'lenta', label: 'Lenta', rate: 0.85 },
  { value: 'normal', label: 'Normal', rate: 1 },
  { value: 'rapida', label: 'Rápida', rate: 1.2 },
];

export const ENGINES = [
  { value: 'auto', label: 'Automático (recomendado)' },
  { value: 'browser', label: 'Del navegador (Chrome, Edge, Safari)' },
  { value: 'server', label: 'Nuestro servidor (Groq Whisper)' },
];

export const DEFAULT_VOICE_SETTINGS = {
  micEnabled: true, // "Hablar en vez de escribir": shows the mic button
  readAloud: true, // "Leer las respuestas en voz alta" after a spoken message
  confirmBeforeSend: true, // "Confirmar antes de enviar" (recommended)
  rate: 'normal',
  lang: 'es-ES',
  engine: 'auto',
  consent: false, // V2 permission sheet already accepted
};

export function normalizeVoiceSettings(raw) {
  const s = { ...DEFAULT_VOICE_SETTINGS };
  if (!raw || typeof raw !== 'object') return s;
  for (const k of ['micEnabled', 'readAloud', 'confirmBeforeSend', 'consent']) {
    if (typeof raw[k] === 'boolean') s[k] = raw[k];
  }
  if (RATES.some((r) => r.value === raw.rate)) s.rate = raw.rate;
  if (ENGINES.some((e) => e.value === raw.engine)) s.engine = raw.engine;
  return s;
}

export const rateValue = (key) => (RATES.find((r) => r.value === key) ?? RATES[1]).rate;

/** "0:07" */
export function formatDuration(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** Which recognizer to use given the setting and what the browser supports. */
export function pickEngine(setting, { hasSpeechRecognition, hasMediaRecorder }) {
  if (setting === 'browser') return hasSpeechRecognition ? 'browser' : null;
  if (setting === 'server') return hasMediaRecorder ? 'server' : null;
  if (hasSpeechRecognition) return 'browser';
  if (hasMediaRecorder) return 'server';
  return null;
}

/** Error codes (Web Speech API, getUserMedia, our server) -> V6 messages. */
export function voiceError(code) {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
    case 'NotAllowedError':
    case 'SecurityError':
      return {
        kind: 'permission',
        title: 'No tengo permiso para el micrófono',
        text: 'Actívalo en los ajustes del navegador (el candado junto a la dirección web) o sigue escribiendo.',
        action: 'write',
      };
    case 'no-speech':
    case 'empty':
      return {
        kind: 'no-speech',
        title: 'No te he oído',
        text: 'No he captado ninguna palabra. Acércate al móvil o busca un sitio con menos ruido.',
        action: 'retry',
      };
    case 'audio-capture':
    case 'NotFoundError':
      return {
        kind: 'no-mic',
        title: 'No encuentro ningún micrófono',
        text: 'Conecta un micrófono o sigue escribiendo.',
        action: 'write',
      };
    case 'unsupported':
      return {
        kind: 'unsupported',
        title: 'Tu navegador no permite hablar aquí',
        text: 'Prueba con Chrome, Edge o Safari, o sigue escribiendo.',
        action: 'write',
      };
    default:
      return {
        kind: 'failed',
        title: 'No he podido convertir tu voz en texto',
        text: 'Tu mensaje no se ha perdido: puedes repetirlo o escribirlo.',
        action: 'retry',
      };
  }
}

const strip = (t) => t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[¡!¿?.,;:]/g, ' ').replace(/\s+/g, ' ').trim();

/** A spoken short answer to a quick-reply question: "sí", "no", "no lo sé". */
export function parseYesNo(text) {
  const t = strip(String(text ?? ''));
  if (!t || t.split(' ').length > 5) return null;
  if (/^(no lo se|no se|ni idea|no estoy segur[oa])\b/.test(t)) return 'No lo sé';
  if (/^(explicamelo|explica(me)?|que es eso|no lo entiendo)\b/.test(t)) return 'Explícamelo';
  if (/^(omitir|salta(r)?|siguiente|despues)\b/.test(t)) return 'Omitir por ahora';
  if (/^(si|claro|correcto|afirmativo|si lo soy|si lo estoy|si esta)\b/.test(t)) return 'Sí';
  if (/^(no|negativo|no lo soy|no lo estoy)\b/.test(t)) return 'No';
  return null;
}

const NUMBER_WORDS = {
  cien: 100, ciento: 100, doscientas: 200, doscientos: 200, trescientas: 300, trescientos: 300,
  cuatrocientas: 400, cuatrocientos: 400, quinientas: 500, quinientos: 500, seiscientas: 600, seiscientos: 600,
  setecientas: 700, setecientos: 700, ochocientas: 800, ochocientos: 800, novecientas: 900, novecientos: 900,
  cincuenta: 50, sesenta: 60, setenta: 70, ochenta: 80, noventa: 90, cuarenta: 40, treinta: 30, veinte: 20,
};

const ANIMALS = [
  [/ovej|ovin|cordero/, 'Ovino'], [/cabra|caprin/, 'Caprino'], [/vaca|bovin|terner/, 'Bovino'],
  [/cerdo|porcin/, 'Porcino'], [/caball|equin|yegua/, 'Equino'], [/gallin|pollo|avicol/, 'Avícola'], [/colmen|abeja|apicol/, 'Apícola'],
];

const PLACES = ['Teruel', 'Huesca', 'Zaragoza', 'Aragón', 'Soria', 'León', 'Burgos', 'Salamanca', 'Zamora', 'Ávila', 'Segovia', 'Valladolid', 'Palencia',
  'Cáceres', 'Badajoz', 'Extremadura', 'Castilla y León', 'Castilla-La Mancha', 'Cuenca', 'Toledo', 'Albacete', 'Ciudad Real', 'Guadalajara',
  'Galicia', 'Lugo', 'Ourense', 'Asturias', 'Cantabria', 'Navarra', 'La Rioja', 'Andalucía', 'Jaén', 'Córdoba', 'Granada', 'Almería',
  'Huelva', 'Sevilla', 'Murcia', 'Cataluña', 'Lleida', 'Madrid'];

const UNITS = { dos: 2, tres: 3, cuatro: 4, cinco: 5, seis: 6, siete: 7, ocho: 8, nueve: 9, diez: 10, quince: 15 };

/** "Tengo unas trescientas ovejas en Teruel" -> 300 (digits or Spanish number words). */
export function extractNumber(text) {
  const t = strip(text);
  const digits = /(\d{1,3}(?:[.\s]\d{3})+|\d+)/.exec(t);
  if (digits) return Number(digits[1].replace(/[.\s]/g, ''));
  let total = 0;
  let current = 0;
  for (const w of t.split(' ')) {
    if (w === 'mil') { total += (current || 1) * 1000; current = 0; }
    else if (NUMBER_WORDS[w]) current += NUMBER_WORDS[w];
    else if (UNITS[w]) current += UNITS[w];
  }
  return total + current || null;
}

/** V4 "He reconocido": hints to double-check numbers and places. */
export function recognizedHints(text) {
  const raw = String(text ?? '');
  const t = strip(raw);
  const hints = [];
  const animal = ANIMALS.find(([re]) => re.test(t));
  const n = extractNumber(raw);
  if (animal && n) hints.push(`${animal[1]} ≈ ${n.toLocaleString('es-ES')} cabezas`);
  else if (animal) hints.push(animal[1]);
  else if (n) hints.push(`Número: ${n.toLocaleString('es-ES')}`);
  for (const p of PLACES) if (t.includes(strip(p))) { hints.push(p); break; }
  return hints;
}

/** Text for speechSynthesis: no markdown, links read as "enlace en pantalla". */
export function textForSpeech(answer) {
  return String(answer ?? '')
    .replace(/https?:\/\/\S+/g, 'el enlace que tienes en pantalla')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/^#{1,4}\s+/gm, '')
    .replace(/^\s*(?:[-•*]|\d+[.)])\s+(.*?)[.;:]?\s*$/gm, '$1.')
    .replace(/[«»*_`#]/g, '')
    .replace(/\s*·\s*/g, ', ')
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, ' ')
    .replace(/([.:!?])\s*\./g, '$1')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

/** Splits long text into sentence chunks: some engines cut utterances after ~15 s. */
export function speechChunks(text, max = 220) {
  const sentences = text.match(/[^.!?]+[.!?]*/g) ?? [];
  const out = [];
  let cur = '';
  for (const s of sentences.map((x) => x.trim()).filter(Boolean)) {
    if ((cur + ' ' + s).trim().length > max && cur) { out.push(cur); cur = s; } else cur = `${cur} ${s}`.trim();
  }
  if (cur) out.push(cur);
  return out;
}

/** Rough reading time for the "Leyendo · 0:12 de 0:27" label (≈ 2.6 words/s at normal speed). */
export function estimateSeconds(text, rateKey = 'normal') {
  const words = String(text).split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / (2.6 * rateValue(rateKey))));
}
