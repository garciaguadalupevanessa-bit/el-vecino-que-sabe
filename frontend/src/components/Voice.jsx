import { useCallback, useEffect, useRef, useState } from 'react';
import { speechSupport, startBrowserRecognition, startServerRecording, speak } from '../lib/speech.js';
import {
  pickEngine, voiceError, recognizedHints, formatDuration, textForSpeech, estimateSeconds, RATES, ENGINES,
} from '../lib/voice.js';

const support = speechSupport();

export function voiceAvailable(settings) {
  return Boolean(pickEngine(settings.engine, support)) && support.secure;
}

/* ---------------- Speech-to-text state machine ---------------- */

export function useVoiceInput({ settings, setSettings, transcribe, onSubmit, onBeforeListen }) {
  const [state, setState] = useState('idle'); // idle | consent | listening | transcribing | confirm | error
  const [interim, setInterim] = useState('');
  const [text, setText] = useState('');
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [duration, setDuration] = useState(0);
  const handle = useRef(null);
  const startedAt = useRef(0);
  const engine = pickEngine(settings.engine, support);

  useEffect(() => {
    if (state !== 'listening') return undefined;
    const t = setInterval(() => setElapsed((Date.now() - startedAt.current) / 1000), 250);
    return () => clearInterval(t);
  }, [state]);

  useEffect(() => () => handle.current?.cancel(), []);

  const finish = useCallback((result) => {
    handle.current = null;
    const secs = (Date.now() - startedAt.current) / 1000;
    setDuration(secs);
    if (result.error) {
      setError(voiceError(result.error));
      setState('error');
      return;
    }
    const clean = result.text.trim();
    if (!settings.confirmBeforeSend) {
      setState('idle');
      onSubmit(clean, { via: 'voz', duration: secs });
      return;
    }
    setText(clean);
    setState('confirm');
  }, [settings.confirmBeforeSend, onSubmit]);

  const listen = useCallback(() => {
    if (!engine || !support.secure) { setError(voiceError('unsupported')); setState('error'); return; }
    onBeforeListen?.();
    setInterim('');
    setText('');
    setError(null);
    setElapsed(0);
    startedAt.current = Date.now();
    setState('listening');
    handle.current = engine === 'browser'
      ? startBrowserRecognition({ lang: settings.lang, onInterim: setInterim, onEnd: finish })
      : startServerRecording({ transcribe, onState: (s) => setState(s), onEnd: finish });
  }, [engine, settings.lang, transcribe, finish, onBeforeListen]);

  const start = () => {
    if (!settings.consent) { setState('consent'); return; }
    listen();
  };

  return {
    state, interim, text, setText, error, elapsed, duration, engine,
    hints: recognizedHints(text),
    start,
    acceptConsent: () => { setSettings((s) => ({ ...s, consent: true })); listen(); },
    declineConsent: () => setState('idle'),
    stop: () => handle.current?.stop(),
    cancel: () => { handle.current?.cancel(); handle.current = null; setState('idle'); },
    send: () => {
      const clean = text.trim();
      if (!clean) return;
      setState('idle');
      onSubmit(clean, { via: 'voz', duration });
    },
    repeat: listen,
    clear: () => { setText(''); setState('idle'); },
    dismiss: () => setState('idle'),
  };
}

export function MicButton({ voice, disabled }) {
  const busy = voice.state === 'listening' || voice.state === 'transcribing';
  return (
    <button
      type="button"
      className={`mic-btn${busy ? ' mic-on' : ''}`}
      onClick={busy ? voice.stop : voice.start}
      disabled={disabled && !busy}
      aria-pressed={busy}
      aria-label={busy ? 'Terminar de hablar' : 'Hablar en vez de escribir'}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-2.08A7 7 0 0 0 19 12h-2Z" />
      </svg>
      <span className="mic-label">{busy ? 'Terminar' : 'Hablar'}</span>
    </button>
  );
}

const HOW_TO_ENABLE = 'Pulsa el candado o el icono junto a la dirección web, busca «Micrófono» y elige «Permitir». Después vuelve a pulsar el botón del micrófono.';

export function VoicePanel({ voice, onWriteInstead }) {
  const textRef = useRef(null);
  const [showHow, setShowHow] = useState(false);
  useEffect(() => { if (voice.state === 'confirm') textRef.current?.focus(); }, [voice.state]);

  if (voice.state === 'idle') return null;

  if (voice.state === 'consent') {
    return (
      <div className="voice-panel" role="dialog" aria-labelledby="vp-consent-title">
        <h3 id="vp-consent-title">Para hablar, necesito usar tu micrófono</h3>
        <ul className="voice-promises">
          <li><span aria-hidden="true">🎙️</span> <span><strong>Solo escucho</strong> mientras el botón está en rojo.</span></li>
          <li><span aria-hidden="true">🗑️</span> <span><strong>No guardamos el audio:</strong> lo convertimos en texto y se borra.</span></li>
          <li><span aria-hidden="true">✍️</span> <span><strong>Tú decides:</strong> antes de enviar, ves lo que he entendido.</span></li>
        </ul>
        <p className="support">
          Ahora tu navegador te preguntará si das permiso.
          {voice.engine === 'browser' && ' En Chrome y Edge, el navegador convierte la voz en texto con su propio servicio.'}
        </p>
        <div className="btn-row">
          <button type="button" className="btn" onClick={voice.acceptConsent} autoFocus>Continuar</button>
          <button type="button" className="btn btn-secondary" onClick={() => { voice.declineConsent(); onWriteInstead(); }}>Ahora no, prefiero escribir</button>
        </div>
      </div>
    );
  }

  if (voice.state === 'listening' || voice.state === 'transcribing') {
    const listening = voice.state === 'listening';
    return (
      <div className="voice-panel voice-listening" role="status" aria-live="polite">
        <div className="voice-head">
          <span className={`rec-dot${listening ? ' rec-live' : ''}`} aria-hidden="true" />
          <h3>{listening ? 'Te escucho…' : 'Convirtiendo tu voz en texto…'}</h3>
        </div>
        {listening && <p>Habla con calma. Pulsa «Terminar» cuando acabes.</p>}
        <p className="eyebrow">Lo que voy entendiendo</p>
        <p className="voice-interim">
          {voice.engine === 'browser'
            ? (voice.interim || <span className="muted">Todavía no he oído nada…</span>)
            : <span className="muted">{listening ? 'Grabando. Lo verás escrito al terminar.' : 'Un momento…'}</span>}
        </p>
        <p className="support">{formatDuration(voice.elapsed)} · se para solo tras 3 s de silencio</p>
        <div className="btn-row">
          <button type="button" className="btn btn-secondary" onClick={voice.cancel}>Cancelar</button>
          {listening && <button type="button" className="btn btn-stop" onClick={voice.stop}>Terminar</button>}
        </div>
      </div>
    );
  }

  if (voice.state === 'confirm') {
    return (
      <div className="voice-panel" role="dialog" aria-labelledby="vp-confirm-title">
        <h3 id="vp-confirm-title">¿He entendido bien?</h3>
        <label htmlFor="vp-text" className="support">Puedes corregir el texto antes de enviarlo</label>
        <textarea id="vp-text" ref={textRef} rows={3} value={voice.text} onChange={(e) => voice.setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); voice.send(); } if (e.key === 'Escape') voice.clear(); }} />
        {voice.hints.length > 0 && (
          <p className="voice-hints"><span className="support">He reconocido:</span> {voice.hints.map((h) => <span key={h} className="badge tone-info">{h}</span>)}</p>
        )}
        <p className="support">Revisa sobre todo números y nombres de lugares: son lo que más se confunde al hablar.</p>
        <div className="btn-row">
          <button type="button" className="btn" onClick={voice.send} disabled={!voice.text.trim()}>Enviar</button>
          <button type="button" className="btn btn-secondary" onClick={voice.repeat}>Repetir</button>
          <button type="button" className="btn btn-ghost" onClick={voice.clear}>Borrar</button>
        </div>
        <p className="support">Mensaje de voz · {formatDuration(voice.duration)}</p>
      </div>
    );
  }

  // error
  const e = voice.error;
  return (
    <div className="voice-panel notice-error" role="alert">
      <h3>{e.title}</h3>
      <p>{e.text}</p>
      {e.kind === 'permission' && showHow && <p className="support">{HOW_TO_ENABLE}</p>}
      <div className="btn-row">
        {e.action === 'retry' && <button type="button" className="btn" onClick={voice.repeat}>Volver a intentarlo</button>}
        {e.kind === 'permission' && !showHow && <button type="button" className="btn btn-secondary" onClick={() => setShowHow(true)}>Cómo activarlo</button>}
        <button type="button" className="btn btn-secondary" onClick={() => { voice.dismiss(); onWriteInstead(); }}>Escribir en su lugar</button>
      </div>
    </div>
  );
}

/* ---------------- Read aloud (V5) ---------------- */

export function useSpeaker(settings) {
  const [speaking, setSpeaking] = useState(null); // { id, total }
  const [elapsed, setElapsed] = useState(0);
  const handle = useRef(null);
  const textRef = useRef('');
  const startedAt = useRef(0);

  useEffect(() => {
    if (!speaking) return undefined;
    const t = setInterval(() => setElapsed((Date.now() - startedAt.current) / 1000), 250);
    return () => clearInterval(t);
  }, [speaking]);

  const stop = useCallback(() => {
    const h = handle.current;
    handle.current = null;
    h?.stop();
    setSpeaking(null);
  }, []);

  const play = useCallback((id, answer, rate = settings.rate) => {
    if (!support.hasSynthesis) return;
    handle.current?.stop();
    const text = textForSpeech(answer);
    textRef.current = answer;
    startedAt.current = Date.now();
    setElapsed(0);
    setSpeaking({ id, total: estimateSeconds(text, rate) });
    const h = speak(text, { rate, lang: settings.lang, onEnd: () => { if (handle.current === h) { handle.current = null; setSpeaking(null); } } });
    handle.current = h;
  }, [settings.rate, settings.lang]);

  useEffect(() => () => handle.current?.stop(), []);

  return { speaking, elapsed, play, stop, supported: support.hasSynthesis, restart: (rate) => speaking && play(speaking.id, textRef.current, rate) };
}

export function ReadAloudBar({ speaker, settings, setSettings }) {
  if (!speaker.speaking) return null;
  const setRate = (r) => { setSettings((s) => ({ ...s, rate: r })); speaker.restart(r); };
  return (
    <div className="read-aloud" role="status" aria-live="off">
      <span className="rec-dot rec-live speaking-dot" aria-hidden="true" />
      <span className="read-label">Leyendo · {formatDuration(Math.min(speaker.elapsed, speaker.speaking.total))} de {formatDuration(speaker.speaking.total)}</span>
      <span className="read-rates" role="group" aria-label="Velocidad de lectura">
        {RATES.map((r) => (
          <button key={r.value} type="button" className="chip chip-small" aria-pressed={settings.rate === r.value} onClick={() => setRate(r.value)}>{r.label}</button>
        ))}
      </span>
      <button type="button" className="btn btn-secondary" onClick={speaker.stop}>Parar</button>
    </div>
  );
}

export function ListenButton({ id, text, speaker }) {
  if (!speaker.supported) return null;
  const on = speaker.speaking?.id === id;
  return (
    <button type="button" className="btn btn-ghost listen-btn" onClick={() => (on ? speaker.stop() : speaker.play(id, text))} aria-pressed={on}>
      <span aria-hidden="true">{on ? '■' : '🔊'}</span> {on ? 'Parar' : 'Escuchar'}
    </button>
  );
}

/* ---------------- Voice settings (V6) ---------------- */

function Toggle({ id, label, hint, checked, onChange }) {
  return (
    <div className="toggle-row">
      <label htmlFor={id} className="toggle">
        <span>
          <strong>{label}</strong>
          {hint && <span className="support toggle-hint">{hint}</span>}
        </span>
        <input id={id} type="checkbox" role="switch" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      </label>
    </div>
  );
}

export function VoiceSettings({ settings, setSettings, speaker, onClose }) {
  const set = (k) => (v) => setSettings((s) => ({ ...s, [k]: v }));
  const engine = pickEngine(settings.engine, support);
  return (
    <section className="coverage-panel voice-settings" aria-labelledby="voice-settings-title">
      <div className="profile-head">
        <h2 id="voice-settings-title">Preferencias de voz</h2>
        <button type="button" className="btn btn-ghost" onClick={onClose}>Cerrar</button>
      </div>
      {!support.secure && <p className="notice notice-warning">La voz solo funciona en páginas seguras (https).</p>}
      {!engine && support.secure && <p className="notice notice-warning">Este navegador no permite hablar con la opción elegida. Prueba otra opción o usa Chrome, Edge o Safari.</p>}
      <Toggle id="vs-mic" label="Hablar en vez de escribir" hint="Muestra el botón del micrófono." checked={settings.micEnabled} onChange={set('micEnabled')} />
      <Toggle id="vs-read" label="Leer las respuestas en voz alta" hint="Cuando me hablas, empiezo a leer la respuesta al llegar." checked={settings.readAloud} onChange={set('readAloud')} />
      <Toggle id="vs-confirm" label="Confirmar antes de enviar" hint="Recomendado: ves el texto antes de mandarlo." checked={settings.confirmBeforeSend} onChange={set('confirmBeforeSend')} />
      <fieldset className="form-section">
        <legend>Velocidad de lectura</legend>
        <div className="segmented">
          {RATES.map((r) => (
            <label key={r.value}>
              <input type="radio" name="vs-rate" value={r.value} checked={settings.rate === r.value} onChange={() => set('rate')(r.value)} />
              <span>{r.label}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="field">
        <label htmlFor="vs-lang">Idioma al hablar</label>
        <select id="vs-lang" value={settings.lang} onChange={() => {}} disabled>
          <option value="es-ES">Español (España)</option>
        </select>
      </div>
      <div className="field">
        <label htmlFor="vs-engine">Reconocimiento de voz</label>
        <select id="vs-engine" value={settings.engine} onChange={(e) => set('engine')(e.target.value)}>
          {ENGINES.map((e) => <option key={e.value} value={e.value}>{e.label}</option>)}
        </select>
        <p className="hint">{engine === 'browser' ? 'Ahora: el navegador (texto en directo).' : engine === 'server' ? 'Ahora: nuestro servidor (texto al terminar).' : 'No disponible en este navegador.'}</p>
      </div>
      {speaker.supported && (
        <button type="button" className="btn btn-secondary" onClick={() => speaker.play('test', 'Hola. Soy El vecino que sabe. Así suena la lectura en voz alta.')}>Probar la lectura</button>
      )}
      <p className="support">El audio no se guarda. Se convierte en texto y se borra; solo queda el texto, como si lo hubieras escrito.</p>
    </section>
  );
}
