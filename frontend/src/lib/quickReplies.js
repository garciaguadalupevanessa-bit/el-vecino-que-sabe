// Quick-reply chips under the assistant's last message (UX v2 · "Respuestas rápidas").

const PROFILE_QUESTIONS = [
  { field: 'agricultor_activo', pattern: /agricultor[a]?\s+activ[oa]/i },
  { field: 'inscrita_rega', pattern: /\bREGA\b/ },
];

/** Looks only at the last question in the answer. */
function lastQuestion(answer) {
  const text = String(answer ?? '');
  const idx = text.lastIndexOf('?');
  if (idx === -1) return '';
  const start = text.lastIndexOf('¿', idx);
  return text.slice(start === -1 ? Math.max(0, idx - 200) : start, idx + 1);
}

/** If the assistant asks a yes/no profile question, which field does it refer to? */
export function detectProfileQuestion(answer) {
  const q = lastQuestion(answer);
  if (!q) return null;
  return PROFILE_QUESTIONS.find((p) => p.pattern.test(q))?.field ?? null;
}

export function quickRepliesFor(answer) {
  if (!lastQuestion(answer)) return [];
  const field = detectProfileQuestion(answer);
  return [
    { label: 'Sí', text: 'Sí.', field, value: true },
    { label: 'No', text: 'No.', field, value: false },
    { label: 'No lo sé', text: 'No lo sé.', field, value: null },
    { label: 'Explícamelo', text: field === 'agricultor_activo' ? '¿Qué es ser agricultor activo? Explícamelo.' : field === 'inscrita_rega' ? '¿Qué es el REGA? Explícamelo.' : 'Explícamelo, por favor.' },
    { label: 'Omitir por ahora', text: 'Prefiero omitirlo por ahora. Sigue con lo que tengas.' },
  ];
}

// Starter prompts on the empty chat. The first one goes straight to the demo case.
export const STARTER_PROMPTS = [
  'Tengo 20 ovejas en extensivo en Teruel y soy agricultor activo.',
  'Tengo una explotación de ovejas.',
  'Busco ayudas para jóvenes agricultores.',
  'Quiero modernizar mi explotación.',
  'Tengo una explotación agrícola.',
];
