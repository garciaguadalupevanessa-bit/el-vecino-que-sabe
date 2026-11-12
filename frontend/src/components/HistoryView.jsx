import { useState } from 'react';
import { formatWhen } from '../lib/conversations.js';

export default function HistoryView({ entries, onOpen, onDelete, onNew }) {
  const [confirmId, setConfirmId] = useState(null);
  return (
    <section className="card history" aria-labelledby="history-title">
      <div className="profile-head">
        <h2 id="history-title">Historial de chats</h2>
        <button type="button" className="btn btn-secondary" onClick={onNew}>+ Nueva conversación</button>
      </div>
      <p className="support">Tus conversaciones se guardan solo en este dispositivo (hasta 20). «Borrar mis datos» las borra todas.</p>

      {entries.length === 0 ? (
        <div className="notice notice-info">
          <p>Todavía no tienes conversaciones guardadas.</p>
          <button type="button" className="btn" onClick={onNew}>Empezar una conversación</button>
        </div>
      ) : (
        <ul className="history-list">
          {entries.map((e) => (
            <li key={e.id} className={`history-item${e.current ? ' history-current' : ''}`}>
              <button type="button" className="history-open" onClick={() => onOpen(e.id)} aria-describedby={`h-meta-${e.id}`}>
                <span className="history-title">{e.title}</span>
              </button>
              <p className="support" id={`h-meta-${e.id}`}>
                {e.current && <strong>Conversación actual · </strong>}
                {formatWhen(e.updatedAt)} · {e.messages === 1 ? '1 mensaje' : `${e.messages} mensajes`}
                {e.aids > 0 && ` · ${e.aids === 1 ? '1 ayuda' : `${e.aids} ayudas`}`}
              </p>
              <div className="btn-row">
                <button type="button" className="btn btn-secondary" onClick={() => onOpen(e.id)}>Abrir<span className="visually-hidden">: {e.title}</span></button>
                {confirmId === e.id ? (
                  <>
                    <button type="button" className="btn btn-danger" onClick={() => { onDelete(e.id); setConfirmId(null); }} autoFocus>Sí, borrarla</button>
                    <button type="button" className="btn btn-ghost" onClick={() => setConfirmId(null)}>Cancelar</button>
                  </>
                ) : (
                  <button type="button" className="btn btn-ghost" onClick={() => setConfirmId(e.id)}>Borrar<span className="visually-hidden">: {e.title}</span></button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
