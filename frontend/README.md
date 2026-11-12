# Frontend · El vecino que sabe

React 18 + Vite + JavaScript. Pure logic in `src/lib/` (tested with the Node test runner); components in `src/components/`.

## Run it

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173 · /api goes to http://localhost:8000
npm run dev:mock   # no backend needed: example answers and aids (demo mode banner shown)
npm test           # node --test
npm run build      # dist/ served by nginx in Docker
```

The proxy target can be changed with `VITE_PROXY_TARGET=http://host:port npm run dev`.

## Rules we follow

- The nginx CSP is strict (`default-src 'self'`, no inline styles): **no `style={...}` props, no external fonts or scripts**. Atkinson Hyperlegible is bundled from `@fontsource`.
- LLM text is rendered as React text nodes (`src/lib/text.js`); never `dangerouslySetInnerHTML`. Only `http(s)` links are rendered.
- Client timeout for `/api/chat`: 90 s. On error the user's message goes back to the input with «Volver a intentarlo».
- Profile and conversation live only in `localStorage` («Borrar mis datos» wipes them). No DNI or bank data is ever asked for.

## Layout

- **Desktop:** collapsible left sidebar (`Sidebar.jsx`: Conversación · Mi explotación · Ayudas · Historial de chats, plus
  «Nueva conversación»), main area with the active section, and «Ayudas encontradas» on the right only next to the chat.
  Collapsed state is kept in `localStorage` (`evqs.ui.v1`).
- **Mobile:** bottom nav with the same four sections and the farm summary strip.
- **Historial de chats:** up to 20 conversations in `localStorage` (`evqs.conversations.v1`, logic in `src/lib/conversations.js`).
  The first-version single chat is migrated automatically. «Borrar mis datos» wipes everything.

## Voice chat (Chat por voz V1–V6)

Mic button (56 px) next to «Enviar» → permission sheet (first time) → «Te escucho…» → «¿He entendido bien?» (editable, with
hints like «Ovino ≈ 300 cabezas · Teruel») → sent through the same `/api/chat`. A spoken «sí / no / no lo sé» answers the
quick-reply question. Answers to spoken messages are read aloud (`speechSynthesis`, es-ES) with Lenta/Normal/Rápida and Parar;
every answer has «Escuchar». Preferences live under «Voz» in the header and in `localStorage`.

Speech-to-text engines (`src/lib/speech.js`), chosen automatically:
- **Browser** (Web Speech API: Chrome, Edge, Safari) → live text while speaking. No backend needed.
- **Server** (`MediaRecorder` → `POST /api/transcribe`, Groq Whisper) → used when the browser has no recognizer (Firefox) or when chosen in «Voz».

Both stop after 3 s of silence or 60 s. The microphone needs **https** (or localhost). Audio is never stored in the browser.

## API contract the frontend expects

`POST /api/chat` with `{ messages: [{ role, content }], profile?: {...} }` (1–30 messages, last one from the user).

Response (the normalizer in `src/lib/aids.js` also accepts English aliases):

```json
{
  "answer": "texto",
  "aids": [{
    "id": "pac-ovino", "nombre": "...", "organismo": "...", "ambito": "estatal",
    "descripcion_corta": "...", "fiabilidad": "verificada|extraida|solo_metadatos",
    "url_fuente": "https://...", "fecha_verificacion": "2026-11-10", "verificado_por": "...",
    "importe": null, "plazo": null, "abierta": true,
    "como_solicitar": "paso 1\npaso 2", "documentacion": ["..."], "alternativas": ["id-b"],
    "resultado": "elegible|condicional|no_elegible",
    "requisitos": [{ "descripcion": "Agricultor activo", "campo": "agricultor_activo", "estado": "cumple|no_cumple|por_confirmar" }],
    "datos_faltantes": ["agricultor_activo"]
  }],
  "sources": [{ "url": "https://...", "nombre": "FEGA", "fecha_verificacion": "2026-11-10" }],
  "trace": [{ "tool": "search_aids", "arguments": { "comunidad": "Aragón" }, "ok": true }]
}
```

The eligibility result may also come nested as `evaluacion: { resultado, requisitos, datos_faltantes }`.
Errors: `422` → «revisa tus datos»; `502` → the backend's `detail` text is shown to the user as is.

`GET /api/aids/{id}` returns one aid (same fields). `GET /api/health` → `{ status, aids_loaded, data_source, llm_configured }`.

### `POST /api/transcribe` (voice option A, to be added in the backend)

`multipart/form-data` with `audio` (webm/opus, mp4 or ogg, ≤ 60 s) and `language=es`. Response: `{ "text": "..." }`.
Suggested implementation: Groq `whisper-large-v3-turbo` via the openai SDK (`client.audio.transcriptions.create`), never
storing the file. `404/501` → the UI says server voice is not available yet; `502` → its `detail` is shown.
`nginx.conf` allows bodies up to 10 MB.
