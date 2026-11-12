import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Chat from './components/Chat.jsx';
import ProfileForm from './components/ProfileForm.jsx';
import AidsPanel from './components/AidsPanel.jsx';
import { AidDetail, ApplicationGuide, Alternatives } from './components/AidViews.jsx';
import { useSpeaker } from './components/Voice.jsx';
import Settings from './components/Settings.jsx';
import { Landing, Login, Signup } from './components/Landing.jsx';
import Sidebar from './components/Sidebar.jsx';
import HistoryView from './components/HistoryView.jsx';
import * as realApi from './lib/api.js';
import { mockSendChat, mockGetAid, mockGetHealth, mockTranscribe } from './lib/mockApi.js';
import { normalizeVoiceSettings, parseYesNo } from './lib/voice.js';
import { quickRepliesFor } from './lib/quickReplies.js';
import { buildChatPayload, validateUserText } from './lib/history.js';
import {
  loadState, saveProfile, clearAll, loadVoiceSettings, saveVoiceSettings,
  loadConversations, saveConversations, dropLegacyChat, loadUi, saveUi, loadDemo, saveDemo,
} from './lib/storage.js';
import * as conv from './lib/conversations.js';
import { profileSummary, boolLabel } from './lib/profile.js';
import { mergeAid } from './lib/aids.js';
import { APP_NAME } from './lib/brand.js';
import { toHash, fromHash } from './lib/routes.js';

// `npm run dev:mock` (vite --mode mock) or VITE_USE_MOCK=true: fake answers, no backend needed.
export const USE_MOCK = import.meta.env.MODE === 'mock' || import.meta.env.VITE_USE_MOCK === 'true';
const api = USE_MOCK
  ? { sendChat: mockSendChat, getAid: mockGetAid, getHealth: mockGetHealth, transcribe: mockTranscribe }
  : { sendChat: realApi.sendChat, getAid: realApi.getAid, getHealth: realApi.getHealth, transcribe: (blob) => realApi.transcribeAudio(blob) };

const storage = (() => { try { return window.localStorage; } catch { return null; } })();
let seq = 0;
const newId = () => `m${Date.now().toString(36)}${(seq++).toString(36)}`;

const FIELD_NAMES = { agricultor_activo: 'agricultor activo', inscrita_rega: 'REGA' };

export default function App() {
  const initial = useMemo(() => {
    const legacy = loadState(storage);
    const conversations = conv.restoreConversations(loadConversations(storage), legacy);
    return { profile: legacy.profile, conversations, current: conv.getCurrent(conversations) };
  }, []);
  // Page in the URL (#/ajustes/voz…) wins on load, so reloads and shared links open the same page.
  const initialLoc = useMemo(() => fromHash(window.location.hash), []);
  const [profile, setProfile] = useState(initial.profile);
  const [convState, setConvState] = useState(initial.conversations);
  const [messages, setMessages] = useState(() => initial.current.messages.map((m) => ({ ...m, id: m.id ?? newId() })));
  const [results, setResults] = useState(initial.current.results);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState('');
  const [section, setSection] = useState(initialLoc?.section ?? 'chat'); // chat | explotacion | ayudas | historial | ajustes
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => loadUi(storage).sidebarCollapsed === true);
  const [bigText, setBigText] = useState(() => loadUi(storage).bigText === true);
  // landing | entrar | crear | app. First visit shows the landing page; returning users go to the app.
  const [screen, setScreen] = useState(() => initialLoc?.screen
    ?? (loadUi(storage).started || initial.current.messages.some((m) => m.role === 'user') ? 'app' : 'landing'));
  const [started, setStarted] = useState(() => loadUi(storage).started === true);
  const [demo, setDemo] = useState(() => loadDemo(storage)); // subscription preview, no real payments
  const [route, setRoute] = useState(initialLoc?.route ? { ...initialLoc.route, from: null } : null); // { name: 'detail'|'guide'|'alternatives', id, from }
  const [details, setDetails] = useState({}); // id -> normalized aid from GET /api/aids/{id}
  const [detailStatus, setDetailStatus] = useState({});
  const [settingsPage, setSettingsPage] = useState(initialLoc?.settingsPage ?? null); // null = Ajustes hub | voz | cobertura | ayuda | terminos | borrar
  const [health, setHealth] = useState(null);
  const [voiceSettings, setVoiceSettings] = useState(() => normalizeVoiceSettings(loadVoiceSettings(storage)));
  const speaker = useSpeaker(voiceSettings);
  const voiceRef = useRef(voiceSettings);
  voiceRef.current = voiceSettings;
  const speakerRef = useRef(speaker);
  speakerRef.current = speaker;
  const inFlight = useRef(null);
  const generation = useRef(0); // bumps when switching conversation: late answers are ignored
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  useEffect(() => { saveProfile(storage, profile); }, [profile]);
  // The active conversation is written back into the history on every change.
  useEffect(() => {
    setConvState((st) => conv.updateCurrent(st, { messages: messages.filter((m) => m.role !== 'note'), results }));
  }, [messages, results]);
  useEffect(() => { if (saveConversations(storage, convState)) dropLegacyChat(storage); }, [convState]);
  useEffect(() => { saveUi(storage, { sidebarCollapsed, bigText, started }); }, [sidebarCollapsed, bigText, started]);
  useEffect(() => { window.scrollTo?.(0, 0); }, [screen]);
  useEffect(() => { saveDemo(storage, demo); }, [demo]);
  useEffect(() => { document.documentElement.dataset.text = bigText ? 'large' : 'normal'; }, [bigText]);
  useEffect(() => { saveVoiceSettings(storage, voiceSettings); }, [voiceSettings]);
  useEffect(() => {
    api.getHealth().then(setHealth).catch(() => setHealth({ status: 'error' }));
  }, []);

  const summary = profileSummary(profile);

  const send = useCallback((text, extraProfile, meta) => {
    const problem = validateUserText(text);
    if (problem) return { error: problem };
    if (inFlight.current) return { error: 'Espera a que termine la búsqueda en curso.' };

    const userMsg = { id: newId(), role: 'user', content: text.trim(), ...(meta?.via ? { via: meta.via, duration: meta.duration } : {}) };
    // Read the latest history from a ref: quick replies add a note right before sending.
    const nextHistory = [...messagesRef.current, userMsg];
    const effectiveProfile = extraProfile ?? profile;
    setMessages((prev) => [...prev, userMsg]);
    setDraft('');
    setError(null);
    setPending(true);
    setSection('chat');
    setRoute(null);

    const controller = new AbortController();
    inFlight.current = controller;
    const gen = generation.current;
    api.sendChat(buildChatPayload(nextHistory, effectiveProfile), { signal: controller.signal })
      .then((res) => {
        if (gen !== generation.current) return;
        const assistantId = newId();
        setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: res.answer, aidsCount: res.aids.length }]);
        // Spoken question -> spoken answer (V5), if the person keeps that preference on.
        if (meta?.via === 'voz' && voiceRef.current.readAloud) speakerRef.current.play(assistantId, res.answer);
        // Keep the last list of aids if this answer has none (e.g. "Explícamelo"), but refresh the trace.
        setResults((prev) => (res.aids.length || !prev ? res : { ...prev, trace: res.trace, sources: res.sources.length ? res.sources : prev.sources }));
        if (res.aids.length) setDetails({});
      })
      .catch((err) => {
        if (gen !== generation.current) return;
        // Spec: the user's text stays in the input so they can retry.
        setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
        setDraft(userMsg.content);
        setError(err);
      })
      .finally(() => { if (gen === generation.current) { setPending(false); inFlight.current = null; } });
    return {};
  }, [profile]);

  const retry = () => send(draft);

  const updateProfileField = (field, value) => {
    const next = { ...profile };
    if (value === true || value === false) next[field] = value;
    else delete next[field];
    setProfile(next);
    return next;
  };

  const quickReply = (chip, questionContext, meta) => {
    let nextProfile;
    if (chip.field && 'value' in chip) {
      nextProfile = updateProfileField(chip.field, chip.value);
      const note = { id: newId(), role: 'note', content: `Anotado: ${FIELD_NAMES[chip.field]} · ${boolLabel(chip.value)}. He actualizado tu explotación.` };
      messagesRef.current = [...messagesRef.current, note];
      setMessages((prev) => [...prev, note]);
    }
    const text = questionContext && chip.field ? `${questionContext} ${chip.text}` : chip.text;
    send(text, nextProfile, meta);
  };

  // A spoken "sí / no / no lo sé" answers the quick-reply question like tapping the chip.
  const sendFromVoice = (text, meta) => {
    const lastAssistant = [...messagesRef.current].reverse().find((m) => m.role === 'assistant');
    const label = parseYesNo(text);
    const chip = label && lastAssistant ? quickRepliesFor(lastAssistant.content).find((c) => c.label === label) : null;
    if (chip) quickReply(chip, undefined, meta);
    else send(text, undefined, meta);
  };

  const fetchDetail = useCallback((id) => {
    if (!id || details[id] || detailStatus[id] === 'loading') return;
    setDetailStatus((s) => ({ ...s, [id]: 'loading' }));
    api.getAid(id)
      .then((aid) => { setDetails((d) => ({ ...d, [id]: aid })); setDetailStatus((s) => ({ ...s, [id]: 'ok' })); })
      .catch(() => setDetailStatus((s) => ({ ...s, [id]: 'error' })));
  }, [details, detailStatus]);

  const aidById = (id) => mergeAid(results?.aids.find((a) => a.id === id) ?? null, details[id] ?? null);

  const open = (name, id) => {
    setRoute((r) => ({ name, id, from: r }));
    fetchDetail(id);
    window.scrollTo?.(0, 0);
  };
  const back = () => setRoute((r) => r?.from ?? null);

  const currentAid = route ? aidById(route.id) : null;
  const altIds = route?.name === 'alternatives' ? (currentAid?.alternativas ?? []) : [];
  useEffect(() => { altIds.forEach((id) => { if (!results?.aids.some((a) => a.id === id)) fetchDetail(id); }); }, [route?.id, route?.name]); // eslint-disable-line react-hooks/exhaustive-deps
  const alternatives = altIds.map(aidById).filter(Boolean);
  const altLoading = altIds.some((id) => detailStatus[id] === 'loading');

  const ask = (text) => { setRoute(null); send(text); };

  // Loads another conversation into the chat (history, new conversation, delete).
  const loadConversation = (state) => {
    inFlight.current?.abort();
    inFlight.current = null;
    generation.current += 1;
    speaker.stop();
    const c = conv.getCurrent(state);
    setConvState(state);
    setMessages(c.messages.map((m) => ({ ...m, id: m.id ?? newId() })));
    setResults(c.results);
    setPending(false); setError(null); setDraft(''); setDetails({}); setRoute(null);
    setSection('chat');
  };
  const newConversation = () => loadConversation(conv.startNew(convState));
  const openConversation = (id) => loadConversation(conv.select(convState, id));
  const deleteConversation = (id) => {
    const next = conv.remove(convState, id);
    if (id === convState.currentId) { loadConversation(next); setSection('historial'); } else setConvState(next);
  };

  const goTo = (key) => { setRoute(null); setSection(key); window.scrollTo?.(0, 0); };
  const openSettings = (page) => { setSettingsPage(page); goTo('ajustes'); };

  // ---- Browser history: every page change is a history entry; Back/Forward restore it. ----
  const currentHash = toHash({ screen, section, settingsPage, route });
  const firstSync = useRef(true);
  useEffect(() => {
    // After Back/Forward the URL already matches the state, so nothing is pushed.
    if (window.location.hash !== currentHash) {
      if (firstSync.current) window.history.replaceState(null, '', currentHash);
      else window.history.pushState(null, '', currentHash);
    }
    firstSync.current = false;
  }, [currentHash]);
  const fetchDetailRef = useRef(fetchDetail);
  fetchDetailRef.current = fetchDetail;
  useEffect(() => {
    const onPop = () => {
      const loc = fromHash(window.location.hash) ?? { screen: 'app', section: 'chat', settingsPage: null, route: null };
      setScreen(loc.screen);
      setSection(loc.section);
      setSettingsPage(loc.settingsPage);
      setRoute(loc.route ? { ...loc.route, from: null } : null);
      if (loc.route) fetchDetailRef.current(loc.route.id);
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  useEffect(() => { if (initialLoc?.route) fetchDetail(initialLoc.route.id); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (screen === 'app' && !started) setStarted(true); }, [screen]); // eslint-disable-line react-hooks/exhaustive-deps

  const doClear = () => {
    clearAll(storage);
    setVoiceSettings(normalizeVoiceSettings(null));
    setDemo({ plan: 'gratis' });
    setBigText(false);
    setStarted(false);
    setScreen('landing');
    setProfile({});
    loadConversation(conv.restoreConversations(null, {}));
    setSettingsPage(null);
  };

  const hasRealConversation = messages.some((m) => m.role === 'user');
  const history = conv.historyEntries(convState);
  const aidsCount = results?.aids.length ?? 0;

  const aidsPanel = (
    <AidsPanel
      results={results} profileSummary={summary}
      onOpen={(id) => open('detail', id)} onAlternatives={(id) => open('alternatives', id)}
      onAnswerMissing={(aid) => send(`Para la ayuda «${aid.nombre}», ¿qué datos me faltan?`)}
      onAskAbout={() => { goTo('chat'); setTimeout(() => document.getElementById('composer-input')?.focus(), 0); }}
      onStateOnly={() => send('Muéstrame solo las ayudas estatales.')}
    />
  );

  let mainContent;
  if (route) {
    mainContent = (
      <div className="col-main">
        {route.name === 'detail' && (
          <AidDetail aid={currentAid} status={detailStatus[route.id]} trace={results?.trace}
            onBack={back} onGuide={(id) => open('guide', id)} onAlternatives={(id) => open('alternatives', id)} onAsk={ask}
            onQuickReply={quickReply} />
        )}
        {route.name === 'guide' && <ApplicationGuide aid={currentAid} status={detailStatus[route.id]} trace={results?.trace} onBack={back} onAsk={ask} />}
        {route.name === 'alternatives' && (
          <Alternatives aid={currentAid} alternatives={alternatives} status={altLoading ? 'loading' : 'ok'} onBack={back} onOpen={(id) => open('detail', id)} onAsk={ask} />
        )}
      </div>
    );
  } else if (section === 'explotacion') {
    mainContent = (
      <div className="col-main col-narrow">
        <ProfileForm
          profile={profile}
          onSave={(p) => setProfile(p)}
          onClear={() => openSettings('borrar')}
          canRecheck={hasRealConversation}
          onRecheck={() => send('He actualizado los datos de mi explotación. ¿Puedes volver a revisar qué ayudas encajan?')}
        />
      </div>
    );
  } else if (section === 'ayudas') {
    mainContent = <div className="col-main col-narrow">{aidsPanel}</div>;
  } else if (section === 'ajustes') {
    mainContent = (
      <div className="col-main col-narrow">
        <Settings
          page={settingsPage} setPage={setSettingsPage} summary={summary}
          voiceSettings={voiceSettings} setVoiceSettings={setVoiceSettings} speaker={speaker}
          health={health} isMock={USE_MOCK} onGo={goTo} onClear={doClear}
          demo={demo} setDemo={setDemo} bigText={bigText} setBigText={setBigText} onAuth={() => setScreen('entrar')}
          onAsk={(text) => { if (text) send(text); else { goTo('chat'); setTimeout(() => document.getElementById('composer-input')?.focus(), 0); } }}
        />
      </div>
    );
  } else if (section === 'historial') {
    mainContent = (
      <div className="col-main col-narrow">
        <HistoryView entries={history} onOpen={openConversation} onDelete={deleteConversation} onNew={newConversation} />
      </div>
    );
  } else {
    mainContent = (
      <>
        <div className="col-main">
          <Chat
            messages={messages} pending={pending} error={error} draft={draft} setDraft={setDraft}
            onSend={(t) => send(t)} onRetry={retry} onQuickReply={(c) => quickReply(c)} onShowAids={() => goTo('ayudas')} profile={profile}
            voiceSettings={voiceSettings} setVoiceSettings={setVoiceSettings} transcribe={api.transcribe}
            onVoiceSubmit={sendFromVoice} speaker={speaker}
          />
        </div>
        <aside className="col-aids" aria-label="Ayudas encontradas">{aidsPanel}</aside>
      </>
    );
  }

  const enterApp = () => { setStarted(true); setScreen('app'); goTo('chat'); };
  if (screen === 'landing') return <Landing onStart={enterApp} onLogin={() => setScreen('entrar')} />;
  if (screen === 'entrar') return <Login onBack={() => setScreen(started ? 'app' : 'landing')} onContinue={enterApp} onSignup={() => setScreen('crear')} />;
  if (screen === 'crear') return <Signup onBack={() => setScreen(started ? 'app' : 'landing')} onContinue={enterApp} onLogin={() => setScreen('entrar')} />;

  return (
    <div className="app">
      <a className="skip-link" href="#main">Saltar al contenido</a>
      <header className="header">
        <a className="brand" href="/" onClick={(e) => { e.preventDefault(); setScreen('landing'); }}>
          <img className="brand-mark" src="/favicon.svg" alt="" width="32" height="32" />
          {APP_NAME}
        </a>
        <button type="button" className="btn btn-ghost header-settings" aria-current={section === 'ajustes' && !route ? 'page' : undefined} onClick={() => openSettings(null)}>
          <svg className="settings-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M19.4 13a7.6 7.6 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a7.3 7.3 0 0 0-1.7-1L15 3h-4l-.3 2.9a7.3 7.3 0 0 0-1.7 1l-2.5-1-2 3.5L6.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1c.5.4 1.1.7 1.7 1L11 21h4l.3-2.9c.6-.3 1.2-.6 1.7-1l2.5 1 2-3.5-2.1-1.6ZM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7Z" transform="translate(-1 0)" /></svg>
          Ajustes
        </button>
      </header>

      {USE_MOCK && <p className="mock-banner">Modo demostración: respuestas y ayudas de ejemplo, sin conexión con el backend.</p>}

      {!route && section !== 'explotacion' && (
        <div className="farm-strip">
          <span>Tu explotación: {summary}</span>
          <button type="button" className="btn btn-ghost" onClick={() => goTo('explotacion')}>Editar</button>
        </div>
      )}

      <div className="shell" data-sidebar={sidebarCollapsed ? 'collapsed' : 'open'}>
        <Sidebar
          section={route ? null : section} onSelect={goTo}
          collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed((c) => !c)}
          onNew={newConversation} summary={summary} aidsCount={aidsCount} historyCount={history.length}
        />
        <main id="main" className="workspace" data-section={route ? 'detail' : section}>
          {mainContent}
        </main>
      </div>

      <footer className="footer">
        {APP_NAME}: información orientativa sobre ayudas públicas. No sustituye a la resolución de la administración ni al asesoramiento profesional.
        <br />Tech for Inclusion Challenge · Ebury × Somos F5
      </footer>

      <nav className="bottom-nav" aria-label="Secciones">
        {[['chat', 'Chat', '💬'], ['ayudas', 'Ayudas', '📋'], ['explotacion', 'Mi explotación', '🌾'], ['historial', 'Historial', '🕘']].map(([key, label, icon]) => (
          <button key={key} type="button" aria-current={!route && section === key ? 'page' : undefined} onClick={() => goTo(key)}>
            <span className="nav-icon" aria-hidden="true">{icon}</span>
            <span>{label}{key === 'ayudas' && aidsCount ? <span className="nav-count">{aidsCount}</span> : null}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
