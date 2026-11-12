// Page addresses in the URL hash, so the browser's Back/Forward buttons, reloads and shared
// links work. Hash routes need no server configuration (nginx serves index.html as is).
//
//   #/                         landing page
//   #/entrar  #/crear-cuenta   sign-in / sign-up preview
//   #/chat  #/explotacion  #/ayudas  #/historial
//   #/ajustes  #/ajustes/<page>            (voz, cobertura, ayuda, terminos, borrar, cuenta, ...)
//   #/ayuda/<id>  #/ayuda/<id>/solicitar  #/ayuda/<id>/alternativas

export const SECTIONS = ['chat', 'explotacion', 'ayudas', 'historial', 'ajustes'];
export const SETTINGS_PAGES = ['voz', 'cobertura', 'ayuda', 'terminos', 'borrar', 'cuenta', 'suscripcion', 'pago', 'pago-ok', 'facturacion'];
const AID_VIEWS = { detail: '', guide: 'solicitar', alternatives: 'alternativas' };
const AID_VIEWS_BACK = Object.fromEntries(Object.entries(AID_VIEWS).map(([k, v]) => [v, k]));

/** { screen, section, settingsPage, route: { name, id } | null } -> "#/..." */
export function toHash({ screen = 'app', section = 'chat', settingsPage = null, route = null } = {}) {
  if (screen === 'landing') return '#/';
  if (screen === 'entrar') return '#/entrar';
  if (screen === 'crear') return '#/crear-cuenta';
  if (route?.id) {
    const view = AID_VIEWS[route.name] ?? '';
    return `#/ayuda/${encodeURIComponent(route.id)}${view ? `/${view}` : ''}`;
  }
  if (section === 'ajustes' && settingsPage) return `#/ajustes/${settingsPage}`;
  return `#/${SECTIONS.includes(section) ? section : 'chat'}`;
}

/** "#/..." -> location object, or null when the hash is empty or unknown. */
export function fromHash(hash) {
  const path = String(hash ?? '').replace(/^#\/?/, '').replace(/\/+$/, '');
  if (!String(hash ?? '').startsWith('#')) return null;
  const parts = path.split('/').filter(Boolean).map((p) => { try { return decodeURIComponent(p); } catch { return p; } });
  const base = { screen: 'app', section: 'chat', settingsPage: null, route: null };
  if (parts.length === 0) return { ...base, screen: 'landing' };
  const [first, second, third] = parts;
  if (first === 'entrar') return { ...base, screen: 'entrar' };
  if (first === 'crear-cuenta') return { ...base, screen: 'crear' };
  if (first === 'ayuda' && second) {
    const name = AID_VIEWS_BACK[third ?? ''];
    return name ? { ...base, section: 'ayudas', route: { name, id: second } } : null;
  }
  if (first === 'ajustes') {
    if (!second) return { ...base, section: 'ajustes' };
    return SETTINGS_PAGES.includes(second) ? { ...base, section: 'ajustes', settingsPage: second } : null;
  }
  return SECTIONS.includes(first) && !second ? { ...base, section: first } : null;
}
