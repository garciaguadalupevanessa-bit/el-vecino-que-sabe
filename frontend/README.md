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
