import { useEffect, useRef, useState } from 'react';
import RichText from './RichText.jsx';
import { STARTER_PROMPTS, quickRepliesFor } from '../lib/quickReplies.js';
import { MAX_CHARS } from '../lib/history.js';
import { starterProgress } from '../lib/profile.js';
import { formatDuration } from '../lib/voice.js';
import { APP_NAME, APP_TAGLINE } from '../lib/brand.js';
import { useVoiceInput, voiceAvailable, MicButton, VoicePanel, ReadAloudBar, ListenButton } from './Voice.jsx';

export function Disclaimer() {
  return (
    <p className="chat-disclaimer">
      <strong>Orientativo:</strong> no garantiza la concesión. La decisión es de la administración; confírmalo en la fuente oficial o en tu oficina comarcal.
    </p>
  );
}

function Welcome({ onPrompt, voiceOn }) {
  return (
    <div className="welcome">
      <h2>Hola. Soy {APP_NAME}.</h2>
      <p>{APP_TAGLINE}</p>
      <ul>
        <li>Buscar ayudas para tu actividad</li>
        <li>Decirte qué cumples y qué falta</li>
        <li>Explicarte cómo pedirlas</li>
      </ul>
      {voiceOn && (
        <div className="notice notice-info voice-intro">
          <p><strong>Puedes escribir o hablar, como te resulte más cómodo.</strong> Para hablar, pulsa el botón verde del micrófono.</p>
          <p className="support">Puedes decir, por ejemplo: «Tengo trescientas ovejas en Teruel», «¿Qué ayudas hay para jóvenes?» o «¿Cómo pido la ayuda?». Si me hablas, te leo las respuestas en voz alta.</p>
        </div>
      )}
      <p><strong>Puedes empezar por aquí:</strong></p>
      <div className="prompt-list">
        {STARTER_PROMPTS.map((p) => (
          <button key={p} type="button" className="chip chip-prompt" onClick={() => onPrompt(p)}>{p}</button>
        ))}
      </div>
      <p className="support">No hace falta registrarse. Lo que me cuentes se guarda solo en este dispositivo.</p>
    </div>
  );
}

function Message({ m, onShowAids, speaker }) {
  if (m.role === 'note') return <p className="msg-note" role="status">✓ {m.content}</p>;
  const isUser = m.role === 'user';
  return (
    <div className={`msg ${isUser ? 'msg-user' : 'msg-assistant'}`}>
      {!isUser && <span className="avatar" aria-hidden="true">EV</span>}
      <div className="bubble">
        <span className="visually-hidden">{isUser ? 'Tú dijiste:' : `${APP_NAME} responde:`}</span>
        {isUser ? <p>{m.content}</p> : <RichText text={m.content} />}
        {isUser && m.via === 'voz' && <p className="bubble-voice">🎙️ Mensaje de voz · {formatDuration(m.duration)}</p>}
        {!isUser && <ListenButton id={m.id} text={m.content} speaker={speaker} />}
        {!isUser && m.aidsCount > 0 && (
          <p className="bubble-meta">
            <button type="button" className="btn btn-secondary" onClick={onShowAids}>
              Ver {m.aidsCount === 1 ? 'la ayuda encontrada' : `las ${m.aidsCount} ayudas encontradas`}
            </button>
          </p>
        )}
      </div>
    </div>
  );
}

const STEPS = ['Buscando en nuestra base de ayudas', 'Revisando los requisitos con tus datos', 'Preparando la respuesta'];

function Loading() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);
  const active = elapsed < 4 ? 0 : elapsed < 12 ? 1 : 2;
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="avatar" aria-hidden="true">EV</span>
      <div className="bubble">
        <p><strong>Buscando ayudas que encajen con tu explotación…</strong></p>
        <ul className="steps">
          {STEPS.map((s, i) => (
            <li key={s} className={i < active ? 'done' : i === active ? 'active' : ''}>
              <span className="dot" aria-hidden="true" />{s}{i < active && <span className="visually-hidden"> (hecho)</span>}
            </li>
          ))}
        </ul>
        <p className="support">{elapsed > 60 ? 'Está tardando más de lo normal. Esperamos hasta 90 segundos.' : 'Suele tardar menos de un minuto.'}</p>
      </div>
    </div>
  );
}

function ErrorBox({ error, onRetry }) {
  return (
    <div className="notice notice-error" role="alert">
      <h3>No hemos podido completar la búsqueda</h3>
      <p>{error.message}</p>
      <button type="button" className="btn" onClick={onRetry}>Volver a intentarlo</button>
    </div>
  );
}

export default function Chat({
  messages, pending, error, draft, setDraft, onSend, onRetry, onQuickReply, onShowAids, profile,
  voiceSettings, setVoiceSettings, transcribe, onVoiceSubmit, speaker,
}) {
  const logRef = useRef(null);
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const [inputError, setInputError] = useState(null);
  const voiceOn = voiceSettings.micEnabled && voiceAvailable(voiceSettings);
  const voice = useVoiceInput({
    settings: voiceSettings, setSettings: setVoiceSettings, transcribe,
    onSubmit: onVoiceSubmit, onBeforeListen: speaker.stop,
  });
  const writeInstead = () => inputRef.current?.focus();

  useEffect(() => {
    // Desktop: the log scrolls inside; mobile: the page scrolls. scrollIntoView covers both.
    if (messages.length || pending || error) endRef.current?.scrollIntoView?.({ block: 'end' });
  }, [messages.length, pending, error]);

  const last = [...messages].reverse().find((m) => m.role === 'assistant' || m.role === 'user');
  const chips = !pending && !error && last?.role === 'assistant' ? quickRepliesFor(last.content) : [];
  const progress = starterProgress(profile);

  const submit = (e) => {
    e.preventDefault();
    const res = onSend(draft);
    setInputError(res?.error ?? null);
    if (!res?.error) inputRef.current?.focus();
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) submit(e);
  };

  return (
    <section className="chat" aria-labelledby="chat-title">
      <h2 id="chat-title" className="visually-hidden">Conversación</h2>
      {messages.length > 0 && progress < 3 && (
        <p className="support">Afina la búsqueda en «Mi explotación»: {progress} de 3 datos (ubicación, actividad y tamaño)</p>
      )}
      <div className="chat-log" ref={logRef} role="log" aria-live="polite" aria-relevant="additions" tabIndex={0} aria-label="Mensajes de la conversación">
        {messages.length === 0 && !pending && <Welcome onPrompt={(p) => onSend(p)} voiceOn={voiceOn} />}
        {messages.map((m) => <Message key={m.id} m={m} onShowAids={onShowAids} speaker={speaker} />)}
        {pending && <Loading />}
        {error && <ErrorBox error={error} onRetry={onRetry} />}
        {chips.length > 0 && (
          <div className="chips" role="group" aria-label="Respuestas rápidas">
            {chips.map((c) => (
              <button key={c.label} type="button" className="chip" onClick={() => onQuickReply(c)}>{c.label}</button>
            ))}
          </div>
        )}
        {chips.length > 0 && voiceOn && <p className="support">También puedes responder hablando: di «sí», «no» o «no lo sé».</p>}
        <div ref={endRef} className="chat-end" />
      </div>

      <div className="composer-stack">
      <ReadAloudBar speaker={speaker} settings={voiceSettings} setSettings={setVoiceSettings} />
      <VoicePanel voice={voice} onWriteInstead={writeInstead} />
      <form className="composer" onSubmit={submit}>
        <label htmlFor="composer-input" className="visually-hidden">Tu mensaje</label>
        <div className="composer-row">
          <textarea
            id="composer-input" ref={inputRef} rows={2} value={draft}
            placeholder={pending ? 'Escribe mientras busco…' : voiceOn ? 'Escribe o habla…' : 'Escribe tu pregunta…'}
            onChange={(e) => { setDraft(e.target.value); setInputError(null); }}
            onKeyDown={onKeyDown}
            aria-invalid={inputError ? 'true' : undefined}
            aria-describedby={inputError ? 'composer-error' : 'composer-counter'}
          />
          {voiceOn && <MicButton voice={voice} disabled={pending} />}
          <button type="submit" className="btn" disabled={pending}>Enviar</button>
        </div>
        {inputError
          ? <p className="field-error" id="composer-error" role="alert">{inputError}</p>
          : <p className="counter support" id="composer-counter">{draft.length > MAX_CHARS - 300 ? `${draft.length} / ${MAX_CHARS}` : 'Pulsa Intro para enviar · Mayús + Intro para salto de línea'}</p>}
      </form>
      <Disclaimer />
      </div>
    </section>
  );
}
