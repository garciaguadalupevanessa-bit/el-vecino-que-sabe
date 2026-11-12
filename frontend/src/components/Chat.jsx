import { useEffect, useRef, useState } from "react";
import { APP_NAME } from "../lib/brand.js";
import Message from "./Message.jsx";

const MAX_CHARS = 2000;
// [chip label, question sent] - user-facing, so Spanish
const SUGGESTIONS = [
  ["¿A qué ayudas puedo optar?", "¿A qué ayudas puedo optar con mi explotación?"],
  ["¿Qué requisitos me faltan?", "¿Qué requisitos me faltan para una ayuda concreta?"],
  ["¿Cómo se solicita?", "¿Cómo se solicita esta ayuda?"],
];

export default function Chat({ messages, sending, error, onSend, onNew }) {
  const [text, setText] = useState("");
  const logRef = useRef(null);
  const areaRef = useRef(null);
  const wasSending = useRef(false);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  // Return focus to the text box when a query ends (not on the initial load)
  useEffect(() => {
    if (wasSending.current && !sending) areaRef.current?.focus();
    wasSending.current = sending;
  }, [sending]);

  const sendText = async () => {
    if (await onSend(text)) setText("");
  };

  return (
    <section className="panel conversation" aria-labelledby="chat-title">
      <div className="chat-header">
        <h2 id="chat-title">Consulta</h2>
        <button type="button" className="secondary" onClick={onNew} disabled={sending}>Nueva conversación</button>
      </div>

      <div ref={logRef} className="chat-log" role="log" aria-live="polite" aria-label="Conversación">
        {messages.length === 0 && (
          <div className="welcome">
            <p><strong>Hola, soy {APP_NAME}.</strong> Puedo buscar ayudas y comparar sus requisitos con los datos de tu explotación.</p>
            <p>Empieza con tu pregunta. Solo te pediré algún dato adicional si ayuda a acotar la búsqueda o comprobar un requisito. También puedes completar el perfil de la izquierda.</p>
          </div>
        )}
        {messages.map((m, i) => <Message key={i} role={m.role} content={m.content} />)}
        {sending && (
          <div className="loading" role="status">Consultando las ayudas y comprobando requisitos…</div>
        )}
      </div>

      {error && <div className="chat-error" role="alert">{error}</div>}

      <div className="chips" aria-label="Preguntas de ejemplo">
        {SUGGESTIONS.map(([label, question]) => (
          <button key={label} type="button" className="chip" disabled={sending} onClick={() => onSend(question)}>
            {label}
          </button>
        ))}
      </div>

      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); sendText(); }}>
        <label htmlFor="input" className="sr-only">Escribe tu pregunta</label>
        <textarea
          id="input" ref={areaRef} rows={2} maxLength={MAX_CHARS} value={text} disabled={sending}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); sendText(); }
          }}
          placeholder="Escribe tu pregunta… (Intro para enviar, Mayús+Intro para salto de línea)"
        />
        <div className="chat-footer">
          <span className="counter" aria-hidden="true">{text.length} / {MAX_CHARS}</span>
          <button type="submit" disabled={sending || !text.trim()}>Enviar</button>
        </div>
      </form>
    </section>
  );
}
