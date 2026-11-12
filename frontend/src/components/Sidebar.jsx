// Collapsible left navigation (desktop). Mobile keeps the bottom nav.

const ICONS = {
  chat: 'M4 4h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H9l-4.3 3.4A.5.5 0 0 1 4 20V5a1 1 0 0 1 1-1Zm2 4v2h12V8H6Zm0 4v2h8v-2H6Z',
  explotacion: 'M12 3 3 9v12h6v-6h6v6h6V9l-9-6Zm0 2.5 7 4.7V19h-2v-6H7v6H5v-8.8l7-4.7Z',
  ayudas: 'M7 3h10a2 2 0 0 1 2 2v16l-7-3-7 3V5a2 2 0 0 1 2-2Zm1 4v2h8V7H8Zm0 4v2h6v-2H8Z',
  historial: 'M13 3a9 9 0 1 0 8.95 10h-2.02A7 7 0 1 1 13 5a6.98 6.98 0 0 1 5.1 2.2L15.3 10H22V3.3l-2.48 2.48A8.97 8.97 0 0 0 13 3Zm-1 4v6.4l4.8 2.9.9-1.5-3.7-2.2V7H12Z',
  nueva: 'M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z',
  ajustes: 'M19.4 13a7.6 7.6 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a7.3 7.3 0 0 0-1.7-1L15 3h-4l-.3 2.9a7.3 7.3 0 0 0-1.7 1l-2.5-1-2 3.5L6.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1c.5.4 1.1.7 1.7 1L11 21h4l.3-2.9c.6-.3 1.2-.6 1.7-1l2.5 1 2-3.5-2.1-1.6ZM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7Z',
  plegar: 'M15.4 6.4 14 5l-7 7 7 7 1.4-1.4L9.8 12l5.6-5.6Z',
  abrir: 'm8.6 17.6 1.4 1.4 7-7-7-7-1.4 1.4 5.6 5.6-5.6 5.6Z',
};

function Icon({ name }) {
  return (
    <svg className="sidebar-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={ICONS[name]} />
    </svg>
  );
}

export const SECTIONS = [
  { key: 'chat', label: 'Conversación' },
  { key: 'explotacion', label: 'Mi explotación' },
  { key: 'ayudas', label: 'Ayudas' },
  { key: 'historial', label: 'Historial de chats' },
  { key: 'ajustes', label: 'Ajustes' },
];

export default function Sidebar({ section, onSelect, collapsed, onToggle, onNew, summary, aidsCount, historyCount }) {
  const extra = { explotacion: summary, ayudas: aidsCount ? `${aidsCount} encontradas` : null, historial: historyCount ? `${historyCount} guardadas` : null };
  return (
    <aside className="sidebar" data-collapsed={collapsed} aria-label="Menú">
      <button
        type="button" className="sidebar-item sidebar-toggle" onClick={onToggle}
        aria-expanded={!collapsed} aria-controls="sidebar-nav" title={collapsed ? 'Abrir menú' : 'Plegar menú'}
      >
        <Icon name={collapsed ? 'abrir' : 'plegar'} />
        <span className="sidebar-label">{collapsed ? 'Abrir menú' : 'Plegar menú'}</span>
      </button>

      <button type="button" className="sidebar-item sidebar-new" onClick={onNew} title="Nueva conversación">
        <Icon name="nueva" />
        <span className="sidebar-label">Nueva conversación</span>
      </button>

      <nav id="sidebar-nav" aria-label="Secciones">
        <ul className="sidebar-list">
          {SECTIONS.map((s) => (
            <li key={s.key}>
              <button
                type="button" className="sidebar-item" onClick={() => onSelect(s.key)}
                aria-current={section === s.key ? 'page' : undefined} title={collapsed ? s.label : undefined}
              >
                <Icon name={s.key} />
                <span className="sidebar-label">
                  <span className="sidebar-text">{s.label}</span>
                  {extra[s.key] && <span className="sidebar-sub">{extra[s.key]}</span>}
                </span>
                {collapsed && s.key === 'ayudas' && aidsCount > 0 && <span className="nav-count sidebar-dot" aria-hidden="true">{aidsCount}</span>}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <p className="sidebar-label sidebar-foot">Se guarda solo en este dispositivo.</p>
    </aside>
  );
}
