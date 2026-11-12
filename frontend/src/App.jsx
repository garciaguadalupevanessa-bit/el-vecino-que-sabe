import { useMemo } from "react";
import Chat from "./components/Chat.jsx";
import ProfileForm from "./components/ProfileForm.jsx";
import ResultPanels from "./components/ResultPanels.jsx";
import ReviewQueue from "./components/ReviewQueue.jsx";
import { useChat } from "./hooks/useChat.js";
import { useLocalStorage } from "./hooks/useLocalStorage.js";
import { APP_NAME, APP_TAGLINE } from "./lib/brand.js";
import { EMPTY_PROFILE, EXAMPLE, normalizeStoredProfile, validateProfile } from "./lib/profile.js";

export default function App() {
  if (window.location.pathname.replace(/\/+$/, "") === "/review") return <ReviewQueue />;
  return <ChatApp />;
}

function ChatApp() {
  const [values, setValues] = useLocalStorage("profile", EMPTY_PROFILE, normalizeStoredProfile);
  const errors = useMemo(() => validateProfile(values), [values]);
  const { messages, results, sending, error, send, reset } = useChat(values);

  return (
    <div className="site-shell">
      <header className="header">
        <a className="brand" href="#inicio" aria-label={`${APP_NAME}, inicio`}>
          <span className="brand-mark" aria-hidden="true">v</span>
          <span>{APP_NAME}</span>
        </a>
        <a className="header-link" href="#asistente">Ir al asistente <span aria-hidden="true">↘</span></a>
      </header>

      <main id="inicio">
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow"><span className="eyebrow-dot" /> Ayudas agrarias, explicadas sin rodeos</p>
            <h1 id="hero-title">La ayuda que buscas, <span>más cerca.</span></h1>
            <p className="hero-description">{APP_TAGLINE} Cuéntanos cómo es tu explotación y te ayudamos a encontrar el siguiente paso.</p>
            <a className="hero-cta" href="#asistente">Encontrar ayudas <span aria-hidden="true">↓</span></a>
          </div>
          <div className="hero-note" aria-label="Cómo funciona El Vecino que Sabe">
            <span className="note-spark" aria-hidden="true">✳</span>
            <p className="note-label">Un buen punto de partida</p>
            <p className="note-copy">Tu explotación<br /><span>+</span> lo que necesitas<br /><span>↓</span><br />Ayudas que encajan</p>
            <div className="note-bottom"><span className="note-avatar" aria-hidden="true">V</span><span>Información clara, decisión tuya</span></div>
          </div>
        </section>

      <p className="notice" role="note">
        Esta herramienta <strong>informa de requisitos, pero no garantiza la concesión</strong>. Confirma siempre
        condiciones y plazos en la fuente oficial o en tu oficina comarcal agraria antes de solicitar.
      </p>

      <section className="workspace" id="asistente" aria-label="Asistente de ayudas agrarias">
        <div className="workspace-heading">
          <div><p className="eyebrow">EMPEZAMOS POR TU EXPLOTACIÓN</p><h2>¿Qué ayuda necesitas encontrar?</h2></div>
          <span className="privacy-note"><span aria-hidden="true">◌</span> Perfil guardado en este dispositivo</span>
        </div>
        <div className="layout">
        <ProfileForm
          values={values}
          errors={errors}
          onChange={setValues}
          onExample={() => setValues(normalizeStoredProfile(EXAMPLE))}
          onClear={() => setValues(normalizeStoredProfile(null))}
        />
        <div>
          <Chat messages={messages} sending={sending} error={error} onSend={send} onNew={reset} />
          <section className="panel results-panel" aria-label="Resultados">
            <ResultPanels {...results} />
          </section>
        </div>
        </div>
      </section>
      </main>

      <footer className="footer">
        <span>Proyecto del Tech for Inclusion Challenge · Ebury × Somos F5</span>
        <span>Los datos pueden haber cambiado. Confirma siempre en la fuente oficial.</span>
      </footer>
    </div>
  );
}
